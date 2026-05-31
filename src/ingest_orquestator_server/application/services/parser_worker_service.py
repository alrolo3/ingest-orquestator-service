from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Lock

from ingest_orquestator_server.application.ports.ingestion_job_repository import (
    IngestionJobRepository,
)
from ingest_orquestator_server.application.services.document_parse_service import (
    DocumentParseService,
)
from ingest_orquestator_server.application.services.embedding_dispatch_service import (
    EmbeddingDispatchService,
)
from ingest_orquestator_server.application.services.stage_logger import log_stage
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.models.ingestion_status import IngestionStatus

logger = logging.getLogger(__name__)


class ParserWorkerService:
    """Thread-backed parser worker pool for API-created ingestion jobs."""

    def __init__(
        self,
        *,
        settings: Settings,
        document_parse_service: DocumentParseService,
        job_repository: IngestionJobRepository,
        dispatch_service: EmbeddingDispatchService,
    ) -> None:
        self._settings = settings
        self._document_parse_service = document_parse_service
        self._job_repository = job_repository
        self._dispatch_service = dispatch_service
        self._executor = ThreadPoolExecutor(
            max_workers=settings.parser_worker_count,
            thread_name_prefix="ingest-parser",
        )
        self._submitted: set[str] = set()
        self._lock = Lock()

    def submit_job(self, job_id: str) -> None:
        with self._lock:
            if job_id in self._submitted:
                return
            self._submitted.add(job_id)
        log_stage(
            "parser.worker.submitted",
            job_id=job_id,
            worker_count=self._settings.parser_worker_count,
        )
        self._executor.submit(self.process_job, job_id)

    def recover_active_jobs(self) -> None:
        for job in self._job_repository.list_by_status(
            {
                IngestionStatus.QUEUED.value,
                IngestionStatus.PARSER_QUEUED.value,
                IngestionStatus.PARSING.value,
                IngestionStatus.PARSED.value,
                IngestionStatus.DISPATCH_QUEUED.value,
                IngestionStatus.DISPATCHING.value,
                IngestionStatus.STORED_LOCAL.value,
                IngestionStatus.INDEXED_ELASTIC.value,
                IngestionStatus.RETRYABLE_FAILURE.value,
            }
        ):
            self.submit_job(job.job_id)

    def process_job(self, job_id: str) -> None:
        job = self._job_repository.get(job_id)
        if job is None:
            self._release_job(job_id)
            return
        if job.input_path is None:
            self._fail_job(job_id, "Queued job has no input path.")
            self._release_job(job_id)
            return

        pipeline = job.metadata.get("requested_pipeline")
        chunking_enabled = job.metadata.get("requested_chunking_enabled")
        chunking_strategy = job.metadata.get("requested_chunking_strategy")

        running_job = job.model_copy(
            update={
                "status": IngestionStatus.PARSING,
                "started_at": job.started_at or datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            }
        )
        self._job_repository.save(running_job)
        log_stage(
            "parser.worker.started",
            job_id=job_id,
            parser=running_job.parser,
            pipeline=pipeline,
            input_path=running_job.input_path,
        )

        try:
            parse_result = self._document_parse_service.parse_file(
                file_path=running_job.input_path,
                parser_name=running_job.parser,
                output_root=None,
                document_id=job_id,
                pipeline=str(pipeline) if pipeline is not None else None,
                chunking_enabled=bool(chunking_enabled) if chunking_enabled is not None else None,
                chunking_strategy=str(chunking_strategy) if chunking_strategy is not None else None,
            )
        except Exception as exc:
            self._fail_job(job_id, str(exc), error_type=type(exc).__name__)
            logger.exception("parser.worker.failed", extra={"job_id": job_id})
            self._release_job(job_id)
            return

        parsed_job = running_job.model_copy(
            update={
                "status": IngestionStatus.PARSED,
                "document_id": parse_result.parse_output.document.document_id,
                "metadata": running_job.metadata | parse_result.diagnostics.metadata,
                "updated_at": datetime.now(UTC),
            }
        )
        self._job_repository.save(parsed_job)
        log_stage(
            "parser.worker.completed",
            job_id=job_id,
            document_id=parse_result.parse_output.document.document_id,
            page_count=parse_result.parse_output.document.page_count,
            element_count=len(parse_result.parse_output.document.elements),
            chunk_count=len(parse_result.chunks),
            embedding_record_count=len(parse_result.embedding_records),
            duration_ms=parse_result.diagnostics.duration_ms,
        )

        queued_job = self._dispatch_service.enqueue_parse_result(parsed_job, parse_result)
        self._job_repository.save(queued_job)
        self._dispatch_service.notify()
        self._release_job(job_id)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=False)

    def _fail_job(
        self,
        job_id: str,
        error: str,
        *,
        error_type: str = "RuntimeError",
    ) -> None:
        job = self._job_repository.get(job_id)
        if job is None:
            return
        failed_job = job.model_copy(
            update={
                "status": IngestionStatus.FAILED,
                "error": error,
                "metadata": job.metadata | {"error_type": error_type},
                "updated_at": datetime.now(UTC),
                "completed_at": datetime.now(UTC),
            }
        )
        self._job_repository.save(failed_job)
        log_stage(
            "parser.worker.failed",
            job_id=job_id,
            error_type=error_type,
            error=error,
        )

    def _release_job(self, job_id: str) -> None:
        with self._lock:
            self._submitted.discard(job_id)
