from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from queue import Empty, Queue
from threading import Lock
from uuid import uuid4

from ingest_orquestator_server.models.embedding_queue import (
    EmbeddingQueueItem,
    EmbeddingQueueItemStatus,
    EmbeddingQueueSnapshot,
)
from ingest_orquestator_server.models.ingestion_job import IngestionJob


class EmbeddingQueueError(RuntimeError):
    pass


class EmbeddingQueueService:
    """Process-local queue for v1.4 embedding handoff MVP."""

    def __init__(self, *, max_bulk_size: int) -> None:
        if max_bulk_size < 1 or max_bulk_size > 5:
            raise ValueError("max_bulk_size must be between 1 and 5")
        self._max_bulk_size = max_bulk_size
        self._queue: Queue[str] = Queue()
        self._items: dict[str, EmbeddingQueueItem] = {}
        self._job_index: dict[str, str] = {}
        self._task_index: dict[str, list[str]] = {}
        self._lock = Lock()

    @property
    def max_bulk_size(self) -> int:
        return self._max_bulk_size

    def enqueue_job(self, job: IngestionJob) -> EmbeddingQueueItem:
        path = self._embedding_input_path(job)
        record_count = self._count_jsonl_records(path)
        if record_count == 0:
            raise EmbeddingQueueError(f"Job {job.job_id} has no embedding records at {path}.")

        with self._lock:
            existing_id = self._job_index.get(job.job_id)
            if existing_id is not None:
                return self._items[existing_id]

            item = EmbeddingQueueItem(
                queue_id=str(uuid4()),
                job_id=job.job_id,
                document_id=job.document_id or job.job_id,
                source_file_name=job.source_file_name,
                embedding_input_path=path,
                output_dir=job.outputs.output_dir if job.outputs is not None else None,
                record_count=record_count,
                metadata={
                    "parser": job.parser,
                    "input_format": job.metadata.get("input_format"),
                    "pipeline": job.metadata.get("pipeline"),
                    "profile": job.metadata.get("profile"),
                    "source_file_name": job.source_file_name,
                },
            )
            self._items[item.queue_id] = item
            self._job_index[job.job_id] = item.queue_id
            self._queue.put(item.queue_id)
            return item

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

    def mark_sent(self, items: list[EmbeddingQueueItem], task_id: str) -> None:
        with self._lock:
            queue_ids: list[str] = []
            for item in items:
                updated = item.model_copy(
                    update={
                        "status": EmbeddingQueueItemStatus.SENT,
                        "task_id": task_id,
                        "last_error": None,
                        "updated_at": datetime.now(UTC),
                    }
                )
                self._items[item.queue_id] = updated
                queue_ids.append(item.queue_id)
            self._task_index[task_id] = queue_ids

    def mark_task_completed(self, task_id: str) -> list[EmbeddingQueueItem]:
        return self._mark_task(task_id, EmbeddingQueueItemStatus.COMPLETED)

    def mark_task_failed(self, task_id: str, error: str) -> list[EmbeddingQueueItem]:
        return self._mark_task(task_id, EmbeddingQueueItemStatus.FAILED, error=error)

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

    def items_for_task(self, task_id: str) -> list[EmbeddingQueueItem]:
        with self._lock:
            return [
                self._items[queue_id]
                for queue_id in self._task_index.get(task_id, [])
                if queue_id in self._items
            ]

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
                if item.status
                in {
                    EmbeddingQueueItemStatus.DISPATCHING,
                    EmbeddingQueueItemStatus.SENT,
                }
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
                queued_count=len(queued),
                in_flight_count=len(in_flight),
                completed_count=len(completed),
                failed_count=len(failed),
                active_task_ids=sorted(self._task_index),
                queued_items=sorted(queued, key=lambda item: item.enqueued_at),
                in_flight_items=sorted(in_flight, key=lambda item: item.updated_at),
                completed_items=sorted(completed, key=lambda item: item.updated_at),
                failed_items=sorted(failed, key=lambda item: item.updated_at),
            )

    def _mark_task(
        self,
        task_id: str,
        status: EmbeddingQueueItemStatus,
        *,
        error: str | None = None,
    ) -> list[EmbeddingQueueItem]:
        updated_items: list[EmbeddingQueueItem] = []
        with self._lock:
            queue_ids = self._task_index.pop(task_id, [])
            for queue_id in queue_ids:
                item = self._items.get(queue_id)
                if item is None:
                    continue
                updated = item.model_copy(
                    update={
                        "status": status,
                        "last_error": error,
                        "updated_at": datetime.now(UTC),
                    }
                )
                self._items[queue_id] = updated
                updated_items.append(updated)
        return updated_items

    @staticmethod
    def _embedding_input_path(job: IngestionJob) -> Path:
        if job.outputs is None or job.outputs.embedding_input_jsonl is None:
            raise EmbeddingQueueError(
                f"Job {job.job_id} does not have embedding_input.jsonl output."
            )
        path = job.outputs.embedding_input_jsonl
        if not path.exists():
            raise EmbeddingQueueError(
                f"Job {job.job_id} embedding input file does not exist: {path}."
            )
        return path

    @staticmethod
    def _count_jsonl_records(path: Path) -> int:
        with path.open(encoding="utf-8") as file:
            return sum(1 for line in file if line.strip())
