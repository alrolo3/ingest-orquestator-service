from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from ingest_orquestator_server.application.ports.ingestion_job_repository import (
    IngestionJobRepository,
)
from ingest_orquestator_server.application.services.document_parse_service import (
    DocumentParseService,
)
from ingest_orquestator_server.application.services.job_parse_coordinator import (
    JobParseCoordinator,
)
from ingest_orquestator_server.application.services.parsed_document_dispatch_service import (
    ParsedDocumentDispatchService,
)
from ingest_orquestator_server.application.services.stage_logger import log_stage
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.models.ingestion_status import IngestionStatus


class ParserWorkerService:
    """Thread-backed parser worker pool for API-created ingestion jobs."""

    def __init__(
        self,
        *,
        settings: Settings,
        document_parse_service: DocumentParseService,
        job_repository: IngestionJobRepository,
        dispatch_service: ParsedDocumentDispatchService,
    ) -> None:
        self._settings = settings
        self._job_repository = job_repository
        self._parse_coordinator = JobParseCoordinator(
            settings=settings,
            document_parse_service=document_parse_service,
            job_repository=job_repository,
            dispatch_service=dispatch_service,
        )
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
        try:
            self._parse_coordinator.process_job(
                job_id,
                preserve_existing_started_at=True,
                fail_missing_input_before_start=True,
            )
        finally:
            self._release_job(job_id)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=False)

    def _release_job(self, job_id: str) -> None:
        with self._lock:
            self._submitted.discard(job_id)
