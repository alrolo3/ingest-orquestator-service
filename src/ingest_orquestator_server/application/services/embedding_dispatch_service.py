from __future__ import annotations

import logging
from datetime import UTC, datetime
from time import perf_counter, sleep

from ingest_orquestator_server.application.ports.embedding_dispatcher import (
    EmbeddingDispatcher,
)
from ingest_orquestator_server.application.ports.ingestion_job_repository import (
    IngestionJobRepository,
)
from ingest_orquestator_server.application.services.embedding_queue_service import (
    EmbeddingQueueError,
    EmbeddingQueueService,
)
from ingest_orquestator_server.application.services.stage_logger import log_stage
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.models.embedding_queue import (
    EmbeddingDispatchRunResult,
    EmbeddingQueueItem,
    EmbeddingTaskStatus,
)
from ingest_orquestator_server.models.ingestion_job import IngestionJob
from ingest_orquestator_server.models.ingestion_status import IngestionStatus

logger = logging.getLogger(__name__)


class EmbeddingDispatchService:
    def __init__(
        self,
        *,
        settings: Settings,
        queue_service: EmbeddingQueueService,
        dispatcher: EmbeddingDispatcher,
        job_repository: IngestionJobRepository,
    ) -> None:
        self._settings = settings
        self._queue_service = queue_service
        self._dispatcher = dispatcher
        self._job_repository = job_repository

    def enqueue_job(self, job: IngestionJob) -> IngestionJob:
        if not self._settings.embedding_queue_enabled:
            log_stage(
                "embedding.queue.skipped",
                job_id=job.job_id,
                document_id=job.document_id,
                reason="embedding queue disabled",
            )
            return job
        try:
            item = self._queue_service.enqueue_job(job)
        except EmbeddingQueueError as exc:
            log_stage(
                "embedding.queue.skipped",
                job_id=job.job_id,
                document_id=job.document_id,
                reason=str(exc),
            )
            logger.warning(
                "embedding.queue.skipped",
                extra={"job_id": job.job_id, "reason": str(exc)},
            )
            return job.model_copy(
                update={
                    "metadata": job.metadata
                    | {
                        "embedding_handoff": {
                            "enabled": True,
                            "queued": False,
                            "reason": str(exc),
                        }
                    },
                    "updated_at": datetime.now(UTC),
                }
            )

        queued_job = job.model_copy(
            update={
                "status": IngestionStatus.EMBEDDING_QUEUED,
                "metadata": self._metadata(
                    job,
                    state=IngestionStatus.EMBEDDING_QUEUED.value,
                    queue_items=[item],
                ),
                "updated_at": datetime.now(UTC),
            }
        )
        self._job_repository.save(queued_job)
        log_stage(
            "embedding.queue.enqueued",
            job_id=job.job_id,
            document_id=item.document_id,
            queue_id=item.queue_id,
            source_file_name=item.source_file_name,
            record_count=item.record_count,
            output_dir=item.output_dir,
        )
        return queued_job

    def run_once(self) -> EmbeddingDispatchRunResult:
        completed_task_ids: list[str] = []
        failed_task_ids: list[str] = []
        for task_id in self._queue_service.snapshot().active_task_ids:
            status = self._dispatcher.get_task_status(task_id)
            if status.completed or status.failed:
                self._complete_remote_task(status)
                if status.failed:
                    failed_task_ids.append(task_id)
                else:
                    completed_task_ids.append(task_id)

        submitted_task_id = self.dispatch_next_batch()
        return EmbeddingDispatchRunResult(
            queue_status=self._queue_service.snapshot(),
            submitted_task_id=submitted_task_id,
            completed_task_ids=completed_task_ids,
            failed_task_ids=failed_task_ids,
        )

    def drain(self) -> EmbeddingDispatchRunResult:
        result = self.run_once()
        if not self._settings.embedding_queue_enabled:
            return result

        started = perf_counter()
        while result.queue_status.queued_count > 0 or result.queue_status.in_flight_count > 0:
            if perf_counter() - started > self._settings.embedding_elastic_task_timeout_seconds:
                return result
            sleep(self._settings.embedding_elastic_task_poll_interval_seconds)
            result = self.run_once()
        return result

    def dispatch_next_batch(self) -> str | None:
        if not self._settings.embedding_queue_enabled:
            return None
        if self._queue_service.snapshot().active_task_ids:
            return None

        batch = self._queue_service.dequeue_batch(self._settings.embedding_queue_max_bulk_size)
        if not batch:
            return None

        for item in batch:
            self._save_item_state(item, IngestionStatus.EMBEDDING_TASK_RUNNING)
        log_stage(
            "embedding.dispatch.started",
            queue_ids=[item.queue_id for item in batch],
            job_ids=[item.job_id for item in batch],
            document_ids=[item.document_id for item in batch],
            document_bulk_size=len(batch),
            record_count=sum(item.record_count for item in batch),
        )

        try:
            result = self._dispatcher.submit_batch(batch)
        except Exception as exc:
            retry = any(
                item.attempts <= self._settings.embedding_elastic_max_retries for item in batch
            )
            updated_items = self._queue_service.mark_batch_failed(
                batch,
                error=str(exc),
                retry=retry,
            )
            status = IngestionStatus.EMBEDDING_QUEUED if retry else IngestionStatus.EMBEDDING_FAILED
            for item in updated_items:
                self._save_item_state(item, status, error=str(exc))
            log_stage(
                "embedding.dispatch.failed",
                queue_ids=[item.queue_id for item in batch],
                job_ids=[item.job_id for item in batch],
                document_ids=[item.document_id for item in batch],
                error_type=type(exc).__name__,
                error=str(exc),
                retry=retry,
            )
            logger.exception("embedding.dispatch.failed")
            return None

        self._queue_service.mark_sent(batch, result.task_id)
        sent_items = self._queue_service.items_for_task(result.task_id)
        for item in sent_items:
            self._save_item_state(
                item,
                IngestionStatus.SENT_TO_EMBEDDING_SYSTEM,
                task_id=result.task_id,
                raw_response=result.raw_response,
            )
        log_stage(
            "embedding.dispatch.accepted",
            task_id=result.task_id,
            queue_ids=[item.queue_id for item in sent_items],
            job_ids=[item.job_id for item in sent_items],
            document_ids=[item.document_id for item in sent_items],
            accepted_document_count=result.accepted_document_count,
        )
        return result.task_id

    def queue_status(self):
        return self._queue_service.snapshot()

    def _complete_remote_task(self, status: EmbeddingTaskStatus) -> None:
        if status.failed:
            items = self._queue_service.mark_task_failed(
                status.task_id,
                status.error or "Remote embedding task failed.",
            )
            for item in items:
                self._save_item_state(
                    item,
                    IngestionStatus.EMBEDDING_FAILED,
                    task_id=status.task_id,
                    error=status.error,
                    raw_response=status.raw_response,
                )
            log_stage(
                "embedding.task.failed",
                task_id=status.task_id,
                queue_ids=[item.queue_id for item in items],
                job_ids=[item.job_id for item in items],
                document_ids=[item.document_id for item in items],
                error=status.error,
            )
            return

        items = self._queue_service.mark_task_completed(status.task_id)
        for item in items:
            self._save_item_state(
                item,
                IngestionStatus.EMBEDDING_COMPLETED,
                task_id=status.task_id,
                raw_response=status.raw_response,
            )
        log_stage(
            "embedding.task.completed",
            task_id=status.task_id,
            queue_ids=[item.queue_id for item in items],
            job_ids=[item.job_id for item in items],
            document_ids=[item.document_id for item in items],
        )

    def _save_item_state(
        self,
        item: EmbeddingQueueItem,
        status: IngestionStatus,
        *,
        task_id: str | None = None,
        error: str | None = None,
        raw_response: dict | None = None,
    ) -> None:
        job = self._job_repository.get(item.job_id)
        if job is None:
            return
        updated = job.model_copy(
            update={
                "status": status,
                "metadata": self._metadata(
                    job,
                    state=status.value,
                    queue_items=[item],
                    task_id=task_id or item.task_id,
                    error=error or item.last_error,
                    raw_response=raw_response,
                ),
                "error": error if status == IngestionStatus.EMBEDDING_FAILED else job.error,
                "updated_at": datetime.now(UTC),
            }
        )
        self._job_repository.save(updated)

    def _metadata(
        self,
        job: IngestionJob,
        *,
        state: str,
        queue_items: list[EmbeddingQueueItem],
        task_id: str | None = None,
        error: str | None = None,
        raw_response: dict | None = None,
    ) -> dict:
        handoff = {
            "enabled": True,
            "state": state,
            "queue_ids": [item.queue_id for item in queue_items],
            "task_id": task_id,
            "document_bulk_size": len(queue_items),
            "record_count": sum(item.record_count for item in queue_items),
            "elastic": self._settings.embedding_queue_config.model_dump(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
        if raw_response is not None:
            handoff["last_response"] = raw_response
        if error:
            handoff["error"] = error
        return job.metadata | {"embedding_handoff": handoff}
