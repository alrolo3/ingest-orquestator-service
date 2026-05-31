from __future__ import annotations

import json
from datetime import UTC, datetime
from queue import Empty, Full, Queue
from threading import Lock
from uuid import uuid4

from ingest_orquestator_server.application.services.document_parse_service import (
    DocumentParseResult,
)
from ingest_orquestator_server.models.embedding_queue import (
    EmbeddingQueueItem,
    EmbeddingQueueItemStatus,
    EmbeddingQueueSnapshot,
)
from ingest_orquestator_server.models.ingestion_job import IngestionJob


class EmbeddingQueueError(RuntimeError):
    pass


class EmbeddingQueueService:
    """Process-local mandatory full-document dispatch queue."""

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
        self._items: dict[str, EmbeddingQueueItem] = {}
        self._job_index: dict[str, str] = {}
        self._lock = Lock()

    @property
    def max_bulk_size(self) -> int:
        return self._max_bulk_size

    def enqueue_parse_result(
        self,
        job: IngestionJob,
        parse_result: DocumentParseResult,
    ) -> EmbeddingQueueItem:
        payload_bytes = self._estimate_payload_bytes(parse_result)
        if self._max_payload_bytes is not None and payload_bytes > self._max_payload_bytes:
            raise EmbeddingQueueError(
                "Dispatch queue payload is too large "
                f"({payload_bytes} bytes > {self._max_payload_bytes} bytes)."
            )
        with self._lock:
            existing_id = self._job_index.get(job.job_id)
            if existing_id is not None:
                return self._items[existing_id]

            item = EmbeddingQueueItem(
                queue_id=str(uuid4()),
                job_id=job.job_id,
                document_id=parse_result.parse_output.document.document_id,
                source_file_name=job.source_file_name,
                parse_output=parse_result.parse_output,
                chunks=parse_result.chunks,
                embedding_records=parse_result.embedding_records,
                diagnostics=parse_result.diagnostics,
                output_dir=job.outputs.output_dir if job.outputs is not None else None,
                record_count=len(parse_result.embedding_records),
                metadata={
                    "parser": job.parser,
                    "input_format": parse_result.diagnostics.metadata.get("input_format"),
                    "pipeline": parse_result.diagnostics.metadata.get("pipeline"),
                    "source_file_name": job.source_file_name,
                    "payload_bytes": payload_bytes,
                },
            )
            self._items[item.queue_id] = item
            self._job_index[job.job_id] = item.queue_id
            try:
                self._queue.put_nowait(item.queue_id)
            except Full as exc:
                self._items.pop(item.queue_id, None)
                self._job_index.pop(job.job_id, None)
                raise EmbeddingQueueError(
                    f"Dispatch queue is full ({self._max_size} items)."
                ) from exc
            return item

    def enqueue_job(self, job: IngestionJob) -> EmbeddingQueueItem:
        raise EmbeddingQueueError(
            "Queue items must contain the full parsed document. Use enqueue_parse_result()."
        )

    def dequeue_batch(self, max_items: int | None = None) -> list[EmbeddingQueueItem]:
        limit = min(max_items or self._max_bulk_size, self._max_bulk_size)
        batch: list[EmbeddingQueueItem] = []
        with self._lock:
            while len(batch) < limit:
                try:
                    queue_id = self._queue.get_nowait()
                except Empty:
                    break
                item = self._items.get(queue_id)
                if item is None or item.status != EmbeddingQueueItemStatus.QUEUED:
                    continue
                updated = item.model_copy(
                    update={
                        "status": EmbeddingQueueItemStatus.DISPATCHING,
                        "attempts": item.attempts + 1,
                        "updated_at": datetime.now(UTC),
                    }
                )
                self._items[queue_id] = updated
                batch.append(updated)
        return batch

    def mark_completed(self, items: list[EmbeddingQueueItem]) -> list[EmbeddingQueueItem]:
        updated_items: list[EmbeddingQueueItem] = []
        with self._lock:
            for item in items:
                updated = item.model_copy(
                    update={
                        "status": EmbeddingQueueItemStatus.COMPLETED,
                        "last_error": None,
                        "updated_at": datetime.now(UTC),
                    }
                )
                self._items[item.queue_id] = updated
                updated_items.append(updated)
        return updated_items

    def mark_batch_failed(
        self,
        items: list[EmbeddingQueueItem],
        *,
        error: str,
        retry: bool,
    ) -> list[EmbeddingQueueItem]:
        updated_items: list[EmbeddingQueueItem] = []
        with self._lock:
            for item in items:
                status = (
                    EmbeddingQueueItemStatus.QUEUED if retry else EmbeddingQueueItemStatus.FAILED
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

    def snapshot(self) -> EmbeddingQueueSnapshot:
        with self._lock:
            queued = [
                item
                for item in self._items.values()
                if item.status == EmbeddingQueueItemStatus.QUEUED
            ]
            in_flight = [
                item
                for item in self._items.values()
                if item.status == EmbeddingQueueItemStatus.DISPATCHING
            ]
            completed = [
                item
                for item in self._items.values()
                if item.status == EmbeddingQueueItemStatus.COMPLETED
            ]
            failed = [
                item
                for item in self._items.values()
                if item.status == EmbeddingQueueItemStatus.FAILED
            ]
            return EmbeddingQueueSnapshot(
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
    def _estimate_payload_bytes(parse_result: DocumentParseResult) -> int:
        payload = {
            "parse_output": parse_result.parse_output.model_dump(
                mode="python",
                exclude={"docling_document"},
            ),
            "chunks": [chunk.model_dump(mode="json") for chunk in parse_result.chunks],
            "embedding_records": [
                record.model_dump(mode="json") for record in parse_result.embedding_records
            ],
            "diagnostics": parse_result.diagnostics.model_dump(mode="json"),
        }
        return len(json.dumps(payload, default=str).encode("utf-8"))
