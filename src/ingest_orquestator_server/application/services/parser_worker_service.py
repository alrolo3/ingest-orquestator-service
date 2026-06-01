from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, ProcessPoolExecutor
from multiprocessing import get_context
from threading import Lock
from typing import Any

from ingest_orquestator_server.application.ports.ingestion_job_repository import (
    IngestionJobRepository,
)
from ingest_orquestator_server.application.services.document_parse_service import (
    DocumentParseService,
)
from ingest_orquestator_server.application.services.job_parse_coordinator import (
    JobParseCoordinator,
    ParseJobResult,
)
from ingest_orquestator_server.application.services.parsed_document_dispatch_service import (
    ParsedDocumentDispatchService,
)
from ingest_orquestator_server.application.services.stage_logger import log_stage
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.models.ingestion_status import IngestionStatus

ParserJobRunner = Callable[[str], ParseJobResult]


class ParserWorkerService:
    """Process-backed parser worker pool for API-created ingestion jobs."""

    def __init__(
        self,
        *,
        settings: Settings,
        job_repository: IngestionJobRepository,
        job_runner: ParserJobRunner | None = None,
        document_parse_service: DocumentParseService | None = None,
        dispatch_service: ParsedDocumentDispatchService | None = None,
        executor: Any | None = None,
    ) -> None:
        self._settings = settings
        self._job_repository = job_repository
        self._parse_coordinator: JobParseCoordinator | None = None
        if document_parse_service is not None and dispatch_service is not None:
            self._parse_coordinator = JobParseCoordinator(
                settings=settings,
                document_parse_service=document_parse_service,
                job_repository=job_repository,
                dispatch_service=dispatch_service,
            )
        if job_runner is None:
            if self._parse_coordinator is None:
                raise ValueError("job_runner is required when parse services are not provided")
            job_runner = self.process_job
        self._job_runner = job_runner
        self._executor = executor or ProcessPoolExecutor(
            max_workers=settings.parser_process_count,
            mp_context=get_context("spawn"),
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
            parser_process_count=self._settings.parser_process_count,
            parser_threads_per_process=self._settings.parser_threads_per_process,
        )
        future = self._executor.submit(self._job_runner, job_id)
        future.add_done_callback(
            lambda completed_future, submitted_job_id=job_id: self._handle_submitted_job_result(
                submitted_job_id,
                completed_future,
            )
        )

    def recover_active_jobs(self) -> None:
        for job in self._job_repository.list_by_status(
            {
                IngestionStatus.QUEUED.value,
                IngestionStatus.PARSER_QUEUED.value,
                IngestionStatus.RETRYING.value,
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

    def process_job(self, job_id: str) -> ParseJobResult:
        try:
            if self._parse_coordinator is None:
                return self._job_runner(job_id)
            return self._parse_coordinator.process_job(
                job_id,
                preserve_existing_started_at=True,
                fail_missing_input_before_start=True,
            )
        finally:
            self._release_job(job_id)

    def _run_submitted_job(self, job_id: str) -> None:
        result = self.process_job(job_id)
        if result.retry_requested:
            self.submit_job(job_id)

    def _handle_submitted_job_result(
        self,
        job_id: str,
        future: Future[ParseJobResult],
    ) -> None:
        try:
            result = future.result()
        except BaseException as exc:
            self._release_job(job_id)
            log_stage(
                "parser.worker.failed",
                job_id=job_id,
                error=str(exc),
                error_type=exc.__class__.__name__,
            )
            return

        self._release_job(job_id)
        if result.retry_requested:
            self.submit_job(job_id)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=False)

    def _release_job(self, job_id: str) -> None:
        with self._lock:
            self._submitted.discard(job_id)
