from __future__ import annotations

import logging
from datetime import UTC, datetime
from threading import Event, Lock, Thread
from time import perf_counter, sleep

from ingest_orquestator_server.application.ports.ingestion_job_repository import (
    IngestionJobRepository,
)
from ingest_orquestator_server.application.ports.job_queue import DispatchJobQueue
from ingest_orquestator_server.application.ports.parse_output_writer import ParseOutputWriter
from ingest_orquestator_server.application.ports.parsed_document_dispatch_sink import (
    ParsedDocumentDispatchSink,
)
from ingest_orquestator_server.application.services.document_parse_service import (
    DocumentParseResult,
)
from ingest_orquestator_server.application.services.ingestion_request_options import (
    dispatch_sink_mode_from_metadata,
)
from ingest_orquestator_server.application.services.parsed_document_dispatch_queue_service import (
    ParsedDocumentDispatchQueueError,
    ParsedDocumentDispatchQueueService,
)
from ingest_orquestator_server.application.services.stage_logger import log_stage
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.models.ingestion_job import IngestionJob
from ingest_orquestator_server.models.ingestion_status import IngestionStatus
from ingest_orquestator_server.models.output_files import OutputFiles
from ingest_orquestator_server.models.parsed_document_dispatch import (
    ParsedDocumentDispatchItem,
    ParsedDocumentDispatchRunResult,
)

logger = logging.getLogger(__name__)


class ParsedDocumentDispatchService:
    def __init__(
        self,
        *,
        settings: Settings,
        queue_service: ParsedDocumentDispatchQueueService,
        dispatcher: ParsedDocumentDispatchSink,
        job_repository: IngestionJobRepository,
        output_writer: ParseOutputWriter,
        dispatch_job_queue: DispatchJobQueue | None = None,
    ) -> None:
        self._settings = settings
        self._queue_service = queue_service
        self._dispatcher = dispatcher
        self._job_repository = job_repository
        self._output_writer = output_writer
        self._dispatch_job_queue = dispatch_job_queue
        self._wake_event = Event()
        self._stop_event = Event()
        self._threads: list[Thread] = []
        self._thread_lock = Lock()

    def start(self) -> None:
        with self._thread_lock:
            self._threads = [thread for thread in self._threads if thread.is_alive()]
            if len(self._threads) >= self._settings.dispatch_worker_count:
                return
            self._stop_event.clear()
            while len(self._threads) < self._settings.dispatch_worker_count:
                worker_number = len(self._threads) + 1
                thread = Thread(
                    target=self._run_loop,
                    name=f"ingest-dispatcher-{worker_number}",
                    daemon=True,
                )
                thread.start()
                self._threads.append(thread)
            log_stage("dispatch.worker.started", worker_count=len(self._threads))

    def stop(self) -> None:
        self._stop_event.set()
        self._wake_event.set()
        for thread in self._threads:
            thread.join(timeout=5)
        stopped_count = len(self._threads)
        self._threads = []
        log_stage("dispatch.worker.stopped", worker_count=stopped_count)

    def notify(self) -> None:
        self.start()
        self._wake_event.set()

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            result = self.run_once()
            if result.queue_status.queued_count == 0:
                self._wake_event.wait(self._settings.dispatch_idle_interval_seconds)
                self._wake_event.clear()
            else:
                sleep(0)

    def enqueue_parse_result(
        self,
        job: IngestionJob,
        parse_result: DocumentParseResult,
    ) -> IngestionJob:
        try:
            item = self._queue_service.enqueue_parse_result(job, parse_result)
        except Exception as exc:
            log_stage(
                "dispatch.queue.failed",
                job_id=job.job_id,
                document_id=parse_result.content.document_id,
                reason=str(exc),
            )
            logger.warning(
                "dispatch.queue.failed",
                extra={"job_id": job.job_id, "reason": str(exc)},
            )
            return job.model_copy(
                update={
                    "status": IngestionStatus.RETRYABLE_FAILURE,
                    "metadata": job.metadata
                    | self._dispatch_metadata(
                        state=IngestionStatus.RETRYABLE_FAILURE.value,
                        queue_items=[],
                        error=str(exc),
                    ),
                    "updated_at": datetime.now(UTC),
                }
            )

        queued_job = job.model_copy(
            update={
                "status": IngestionStatus.DISPATCH_QUEUED,
                "document_id": item.document_id,
                "metadata": job.metadata
                | parse_result.diagnostics.metadata
                | self._dispatch_metadata(
                    state=IngestionStatus.DISPATCH_QUEUED.value,
                    queue_items=[item],
                ),
                "updated_at": datetime.now(UTC),
            }
        )
        self._job_repository.save(queued_job)

        try:
            if self._dispatch_job_queue is not None:
                self._dispatch_job_queue.enqueue_dispatch_job(item)
        except Exception as exc:
            failed_job = queued_job.model_copy(
                update={
                    "status": IngestionStatus.RETRYABLE_FAILURE,
                    "metadata": queued_job.metadata
                    | self._dispatch_metadata(
                        state=IngestionStatus.RETRYABLE_FAILURE.value,
                        queue_items=[item],
                        error=str(exc),
                    ),
                    "updated_at": datetime.now(UTC),
                }
            )
            self._job_repository.save(failed_job)
            log_stage(
                "dispatch.queue.failed",
                job_id=job.job_id,
                document_id=item.document_id,
                reason=str(exc),
            )
            logger.warning(
                "dispatch.queue.failed",
                extra={"job_id": job.job_id, "reason": str(exc)},
            )
            return failed_job

        log_stage(
            "dispatch.queue.enqueued",
            job_id=job.job_id,
            document_id=item.document_id,
            queue_id=item.queue_id,
            source_file_name=item.source_file_name,
            record_count=item.record_count,
            sink_mode=self._sink_mode_for_item(item),
        )
        return queued_job

    def enqueue_job(self, job: IngestionJob) -> IngestionJob:
        raise ParsedDocumentDispatchQueueError(
            "Dispatch queue requires the full parsed document. Use enqueue_parse_result()."
        )

    def run_once(self) -> ParsedDocumentDispatchRunResult:
        submitted_document_count = self.dispatch_next_batch()
        return ParsedDocumentDispatchRunResult(
            queue_status=self._queue_service.snapshot(),
            submitted_document_count=submitted_document_count,
        )

    def drain(self) -> ParsedDocumentDispatchRunResult:
        result = self.run_once()
        while result.queue_status.queued_count > 0 or result.queue_status.in_flight_count > 0:
            result = self.run_once()
        return result

    def dispatch_next_batch(self) -> int:
        batch = self._queue_service.dequeue_batch(self._settings.dispatch_max_bulk_size)
        if not batch:
            return 0
        return self._dispatch_batch(batch, update_queue=True)

    def dispatch_item(self, item: ParsedDocumentDispatchItem) -> int:
        return self._dispatch_batch([item], update_queue=False)

    def _dispatch_batch(
        self, batch: list[ParsedDocumentDispatchItem], *, update_queue: bool
    ) -> int:
        started = perf_counter()
        skipped_queue_ids = {
            item.queue_id
            for item in batch
            if self._job_repository.get(item.job_id) is None
        }
        if skipped_queue_ids:
            skipped = [item for item in batch if item.queue_id in skipped_queue_ids]
            if update_queue:
                self._queue_service.mark_completed(skipped)
            log_stage(
                "dispatch.skipped.deleted_job",
                queue_ids=[item.queue_id for item in skipped],
                job_ids=[item.job_id for item in skipped],
            )
            batch = [item for item in batch if item.queue_id not in skipped_queue_ids]
            if not batch:
                return 0

        for item in batch:
            self._save_item_state(item, IngestionStatus.DISPATCHING)
        sink_modes = self._sink_modes(batch)
        log_stage(
            "dispatch.started",
            queue_ids=[item.queue_id for item in batch],
            job_ids=[item.job_id for item in batch],
            document_ids=[item.document_id for item in batch],
            document_bulk_size=len(batch),
            record_count=sum(item.record_count for item in batch),
            sink_mode=sink_modes[0] if len(sink_modes) == 1 else "mixed",
            sink_modes=sink_modes,
        )

        try:
            local_items = [
                item
                for item in batch
                if self._should_store_local_for(self._sink_mode_for_item(item))
            ]
            elastic_items = [
                item
                for item in batch
                if self._should_dispatch_elastic_for(self._sink_mode_for_item(item))
            ]
            elastic_queue_ids = {item.queue_id for item in elastic_items}
            local_outputs = self._store_local(local_items) if local_items else {}
            result = self._dispatcher.submit_batch(elastic_items) if elastic_items else None
        except Exception as exc:
            retry = any(item.attempts <= self._settings.dispatch_max_retries for item in batch)
            updated_items = (
                self._queue_service.mark_batch_failed(batch, error=str(exc), retry=retry)
                if update_queue
                else batch
            )
            status = IngestionStatus.DISPATCH_QUEUED if retry else IngestionStatus.FAILED
            for item in updated_items:
                self._save_item_state(item, status, error=str(exc))
            log_stage(
                "dispatch.failed",
                queue_ids=[item.queue_id for item in batch],
                job_ids=[item.job_id for item in batch],
                document_ids=[item.document_id for item in batch],
                error_type=type(exc).__name__,
                error=str(exc),
                retry=retry,
            )
            logger.exception("dispatch.failed")
            if update_queue:
                return 0
            raise

        for item in batch:
            outputs = local_outputs.get(item.queue_id)
            metadata = {
                "local_outputs": outputs.model_dump(mode="json") if outputs is not None else None,
                "elastic_response": result.raw_response
                if result is not None and item.queue_id in elastic_queue_ids
                else None,
            }
            self._save_item_state(
                item,
                IngestionStatus.COMPLETED,
                outputs=outputs,
                raw_response=metadata,
            )
        completed_items = self._queue_service.mark_completed(batch) if update_queue else batch
        accepted_document_count = (
            (result.accepted_document_count if result is not None else 0)
            + sum(
                1
                for item in batch
                if self._should_store_local_for(self._sink_mode_for_item(item))
                and not self._should_dispatch_elastic_for(self._sink_mode_for_item(item))
            )
        )
        log_stage(
            "dispatch.completed",
            queue_ids=[item.queue_id for item in completed_items],
            job_ids=[item.job_id for item in completed_items],
            document_ids=[item.document_id for item in completed_items],
            accepted_document_count=accepted_document_count,
            accepted_record_count=(result.accepted_record_count if result else 0),
            sink_mode=sink_modes[0] if len(sink_modes) == 1 else "mixed",
            sink_modes=sink_modes,
            elapsed_ms=round((perf_counter() - started) * 1000),
        )
        return accepted_document_count

    def queue_status(self):
        return self._queue_service.snapshot()

    def _save_item_state(
        self,
        item: ParsedDocumentDispatchItem,
        status: IngestionStatus,
        *,
        error: str | None = None,
        raw_response: dict | None = None,
        outputs: OutputFiles | None = None,
    ) -> None:
        job = self._job_repository.get(item.job_id)
        if job is None:
            return
        updated = job.model_copy(
            update={
                "status": status,
                "outputs": outputs or job.outputs,
                "metadata": job.metadata
                | self._dispatch_metadata(
                    state=status.value,
                    queue_items=[item],
                    error=error or item.last_error,
                    raw_response=raw_response,
                ),
                "error": error if status == IngestionStatus.FAILED else job.error,
                "updated_at": datetime.now(UTC),
                "completed_at": datetime.now(UTC)
                if status == IngestionStatus.COMPLETED
                else job.completed_at,
            }
        )
        self._job_repository.save(updated)

    def _dispatch_metadata(
        self,
        state: str,
        queue_items: list[ParsedDocumentDispatchItem],
        error: str | None = None,
        raw_response: dict | None = None,
    ) -> dict:
        sink_mode = self._sink_mode_for_items(queue_items)
        handoff = {
            "enabled": True,
            "state": state,
            "sink_mode": sink_mode,
            "queue_ids": [item.queue_id for item in queue_items],
            "document_bulk_size": len(queue_items),
            "record_count": sum(item.record_count for item in queue_items),
            "dispatch": self._settings.dispatch_config.model_dump(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
        if raw_response is not None:
            handoff["last_response"] = raw_response
        if error:
            handoff["error"] = error
        return {"dispatch_handoff": handoff}

    def _sink_mode_for_item(self, item: ParsedDocumentDispatchItem) -> str:
        return dispatch_sink_mode_from_metadata(
            item.metadata,
            default=self._settings.dispatch_sink_mode,
        )

    def _sink_mode_for_items(self, items: list[ParsedDocumentDispatchItem]) -> str:
        sink_modes = self._sink_modes(items)
        if len(sink_modes) == 1:
            return sink_modes[0]
        return "mixed"

    def _sink_modes(self, items: list[ParsedDocumentDispatchItem]) -> list[str]:
        if not items:
            return [self._settings.dispatch_sink_mode]
        return sorted({self._sink_mode_for_item(item) for item in items})

    @staticmethod
    def _should_store_local_for(sink_mode: str) -> bool:
        return sink_mode in {"local", "local_and_elastic"}

    @staticmethod
    def _should_dispatch_elastic_for(sink_mode: str) -> bool:
        return sink_mode in {"elastic", "local_and_elastic"}

    def _store_local(self, batch: list[ParsedDocumentDispatchItem]) -> dict[str, OutputFiles]:
        outputs_by_queue_id: dict[str, OutputFiles] = {}
        for item in batch:
            content = item.content.model_copy(
                update={
                    "metadata": item.content.metadata
                    | {
                        "dispatch": {
                            "sink_mode": self._sink_mode_for_item(item),
                            "queue_id": item.queue_id,
                        }
                    }
                }
            )
            outputs = self._output_writer.write(
                content,
                self._settings.outputs_dir,
                diagnostics=item.diagnostics,
            )
            outputs_by_queue_id[item.queue_id] = outputs
            self._save_item_state(item, IngestionStatus.STORED_LOCAL, outputs=outputs)
            log_stage(
                "dispatch.local.stored",
                job_id=item.job_id,
                document_id=item.document_id,
                queue_id=item.queue_id,
                output_dir=outputs.output_dir,
            )
        return outputs_by_queue_id
