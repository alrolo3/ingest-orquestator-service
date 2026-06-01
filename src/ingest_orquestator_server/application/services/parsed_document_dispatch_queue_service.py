from __future__ import annotations

import json
from datetime import UTC, datetime
from queue import Empty, Full, Queue
from threading import Lock
from uuid import uuid4

from ingest_orquestator_server.application.services.document_parse_service import (
    DocumentParseResult,
)
from ingest_orquestator_server.models.ingestion_job import IngestionJob
from ingest_orquestator_server.models.parsed_document_dispatch import (
    ParsedDocumentDispatchItem,
    ParsedDocumentDispatchItemStatus,
    ParsedDocumentDispatchQueueSnapshot,
)


class ParsedDocumentDispatchQueueError(RuntimeError):
    pass


class ParsedDocumentDispatchQueueService:
    """Process-local queue for parsed document dispatch handoff items."""

    def __init__(
        self,
        *,
        max_bulk_size: int,
        max_size: int = 100,
        max_payload_bytes: int | None = None,
    ) -> None:
        if max_bulk_size < 1 or max_bulk_size > 5:
            raise ValueError("max_bulk_size must be between 1 and 5")
        if max_size < 1:
            raise ValueError("max_size must be positive")
        if max_payload_bytes is not None and max_payload_bytes < 1:
            raise ValueError("max_payload_bytes must be positive when configured")
        self._max_bulk_size = max_bulk_size
        self._max_size = max_size
        self._max_payload_bytes = max_payload_bytes
        self._queue: Queue[str] = Queue(maxsize=max_size)
        self._items: dict[str, ParsedDocumentDispatchItem] = {}
        self._job_index: dict[str, str] = {}
        self._lock = Lock()

    @property
    def max_bulk_size(self) -> int:
        return self._max_bulk_size

    def enqueue_parse_result(
        self,
        job: IngestionJob,
        parse_result: DocumentParseResult,
    ) -> ParsedDocumentDispatchItem:
        content = parse_result.content.model_copy(
            update={
                "metadata": parse_result.content.metadata
                | {
                    "job_id": job.job_id,
                    "source_file_name": job.source_file_name,
                    "parser": job.parser,
                    "requested_dispatch_sink_mode": job.metadata.get(
                        "requested_dispatch_sink_mode"
                    ),
                }
            }
        )
        payload_bytes = self._estimate_payload_bytes(content, parse_result)
        if self._max_payload_bytes is not None and payload_bytes > self._max_payload_bytes:
            raise ParsedDocumentDispatchQueueError(
                "Dispatch queue payload is too large "
                f"({payload_bytes} bytes > {self._max_payload_bytes} bytes)."
            )
        with self._lock:
            existing_id = self._job_index.get(job.job_id)
            if existing_id is not None:
                return self._items[existing_id]

            item = ParsedDocumentDispatchItem(
                queue_id=str(uuid4()),
                job_id=job.job_id,
                document_id=content.document_id,
                source_file_name=job.source_file_name,
                content=content,
                diagnostics=parse_result.diagnostics,
                output_dir=job.outputs.output_dir if job.outputs is not None else None,
                record_count=len(content.rag_records),
                metadata={
                    "parser": job.parser,
                    "input_format": parse_result.diagnostics.metadata.get("input_format"),
                    "pipeline": parse_result.diagnostics.metadata.get("pipeline"),
                    "source_file_name": job.source_file_name,
                    "payload_bytes": payload_bytes,
                    "requested_dispatch_sink_mode": job.metadata.get(
                        "requested_dispatch_sink_mode"
                    ),
                },
            )
            self._items[item.queue_id] = item
            self._job_index[job.job_id] = item.queue_id
            try:
                self._queue.put_nowait(item.queue_id)
            except Full as exc:
                self._items.pop(item.queue_id, None)
                self._job_index.pop(job.job_id, None)
                raise ParsedDocumentDispatchQueueError(
                    f"Dispatch queue is full ({self._max_size} items)."
                ) from exc
            return item

    def enqueue_job(self, job: IngestionJob) -> ParsedDocumentDispatchItem:
        raise ParsedDocumentDispatchQueueError(
            "Queue items must contain the full parsed document. Use enqueue_parse_result()."
        )

    def remove_by_job_id(self, job_id: str) -> bool:
        with self._lock:
            queue_id = self._job_index.pop(job_id, None)
            if queue_id is None:
                return False
            self._items.pop(queue_id, None)
            return True

    def dequeue_batch(
        self, max_items: int | None = None
    ) -> list[ParsedDocumentDispatchItem]:
        limit = min(max_items or self._max_bulk_size, self._max_bulk_size)
        batch: list[ParsedDocumentDispatchItem] = []
        with self._lock:
            while len(batch) < limit:
                try:
                    queue_id = self._queue.get_nowait()
                except Empty:
                    break
                item = self._items.get(queue_id)
                if item is None or item.status != ParsedDocumentDispatchItemStatus.QUEUED:
                    continue
                updated = item.model_copy(
                    update={
                        "status": ParsedDocumentDispatchItemStatus.DISPATCHING,
                        "attempts": item.attempts + 1,
                        "updated_at": datetime.now(UTC),
                    }
                )
                self._items[queue_id] = updated
                batch.append(updated)
        return batch

    def mark_completed(
        self, items: list[ParsedDocumentDispatchItem]
    ) -> list[ParsedDocumentDispatchItem]:
        updated_items: list[ParsedDocumentDispatchItem] = []
        with self._lock:
            for item in items:
                updated = item.model_copy(
                    update={
                        "status": ParsedDocumentDispatchItemStatus.COMPLETED,
                        "last_error": None,
                        "updated_at": datetime.now(UTC),
                    }
                )
                self._items[item.queue_id] = updated
                updated_items.append(updated)
        return updated_items

    def mark_batch_failed(
        self,
        items: list[ParsedDocumentDispatchItem],
        *,
        error: str,
        retry: bool,
    ) -> list[ParsedDocumentDispatchItem]:
        updated_items: list[ParsedDocumentDispatchItem] = []
        with self._lock:
            for item in items:
                status = (
                    ParsedDocumentDispatchItemStatus.QUEUED
                    if retry
                    else ParsedDocumentDispatchItemStatus.FAILED
                )
                updated = item.model_copy(
                    update={
                        "status": status,
                        "last_error": error,
                        "updated_at": datetime.now(UTC),
                    }
                )
                self._items[item.queue_id] = updated
                if retry:
                    self._queue.put(item.queue_id)
                updated_items.append(updated)
        return updated_items

    def snapshot(self) -> ParsedDocumentDispatchQueueSnapshot:
        with self._lock:
            queued = [
                item
                for item in self._items.values()
                if item.status == ParsedDocumentDispatchItemStatus.QUEUED
            ]
            in_flight = [
                item
                for item in self._items.values()
                if item.status == ParsedDocumentDispatchItemStatus.DISPATCHING
            ]
            completed = [
                item
                for item in self._items.values()
                if item.status == ParsedDocumentDispatchItemStatus.COMPLETED
            ]
            failed = [
                item
                for item in self._items.values()
                if item.status == ParsedDocumentDispatchItemStatus.FAILED
            ]
            return ParsedDocumentDispatchQueueSnapshot(
                max_bulk_size=self._max_bulk_size,
                max_size=self._max_size,
                max_payload_bytes=self._max_payload_bytes,
                queued_count=len(queued),
                in_flight_count=len(in_flight),
                completed_count=len(completed),
                failed_count=len(failed),
                queued_items=sorted(queued, key=lambda item: item.enqueued_at),
                in_flight_items=sorted(in_flight, key=lambda item: item.updated_at),
                completed_items=sorted(completed, key=lambda item: item.updated_at),
                failed_items=sorted(failed, key=lambda item: item.updated_at),
            )

    @staticmethod
    def _estimate_payload_bytes(
        content,
        parse_result: DocumentParseResult,
    ) -> int:
        payload = {
            "content": content.model_dump(mode="json"),
            "diagnostics": parse_result.diagnostics.model_dump(mode="json"),
        }
        return len(json.dumps(payload, default=str).encode("utf-8"))
