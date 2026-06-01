from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from ingest_orquestator_server.application.ports.ingestion_job_repository import (
    IngestionJobRepository,
)
from ingest_orquestator_server.application.services.document_parse_service import (
    DocumentParseService,
)
from ingest_orquestator_server.application.services.ingestion_job_metadata import (
    build_error_metadata,
)
from ingest_orquestator_server.application.services.ingestion_request_options import (
    ocr_languages_from_metadata,
)
from ingest_orquestator_server.application.services.job_progress_reporter import (
    JobProgressReporter,
)
from ingest_orquestator_server.application.services.parsed_document_dispatch_service import (
    ParsedDocumentDispatchService,
)
from ingest_orquestator_server.application.services.stage_logger import log_stage
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.models.ingestion_job import IngestionJob
from ingest_orquestator_server.models.ingestion_status import IngestionStatus

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RequestedParseOptions:
    pipeline: object
    chunking_enabled: object
    chunking_strategy: object
    ocr_languages: list[str] | None
    include_html: bool


class JobParseCoordinator:
    """Coordinates the persisted job parse lifecycle shared by ingestion entrypoints."""

    def __init__(
        self,
        *,
        settings: Settings,
        document_parse_service: DocumentParseService,
        job_repository: IngestionJobRepository,
        dispatch_service: ParsedDocumentDispatchService | None,
        include_validation_error_metadata: bool = False,
    ) -> None:
        self._document_parse_service = document_parse_service
        self._job_repository = job_repository
        self._dispatch_service = dispatch_service
        self._include_validation_error_metadata = include_validation_error_metadata
        self._progress_reporter = JobProgressReporter(
            job_repository=job_repository,
            history_limit=settings.progress_history_limit,
        )

    def process_job(
        self,
        job_id: str,
        *,
        preserve_existing_started_at: bool,
        fail_missing_input_before_start: bool = False,
        log_parse_started: bool = False,
        log_started_input_path: bool = True,
        log_completed_context: bool = False,
        log_failed_parser: bool = False,
    ) -> None:
        job = self._job_repository.get(job_id)
        if job is None:
            return
        if fail_missing_input_before_start and job.input_path is None:
            self._fail_job(
                job,
                error="Queued job has no input path.",
                error_type="RuntimeError",
                log_parser=log_failed_parser,
            )
            return

        requested = self._requested_parse_options(job)
        now = datetime.now(UTC)
        running_job = job.model_copy(
            update={
                "status": IngestionStatus.PARSING,
                "started_at": (job.started_at or now) if preserve_existing_started_at else now,
                "updated_at": now,
            }
        )
        self._job_repository.save(running_job)
        started_fields = {
            "job_id": job_id,
            "parser": running_job.parser,
            "pipeline": requested.pipeline,
        }
        if log_started_input_path:
            started_fields["input_path"] = running_job.input_path
        log_stage("parser.worker.started", **started_fields)

        try:
            if running_job.input_path is None:
                raise FileNotFoundError("Queued job has no input path.")
            if log_parse_started:
                log_stage(
                    "parser.worker.parse.started",
                    job_id=job_id,
                    parser=running_job.parser,
                    pipeline=requested.pipeline,
                    input_path=running_job.input_path,
                )
            parse_result = self._document_parse_service.parse_file(
                file_path=running_job.input_path,
                parser_name=running_job.parser,
                output_root=None,
                document_id=job_id,
                pipeline=self._optional_string(requested.pipeline),
                chunking_enabled=self._optional_bool(requested.chunking_enabled),
                chunking_strategy=self._optional_string(requested.chunking_strategy),
                ocr_languages=requested.ocr_languages,
                include_html=requested.include_html,
                progress_callback=self._progress_reporter.callback_for(job_id),
            )
        except Exception as exc:
            latest_job = self._job_repository.get(job_id) or running_job
            self._fail_job(
                latest_job,
                error=str(exc),
                error_type=type(exc).__name__,
                exc=exc,
                log_parser=log_failed_parser,
            )
            extra = {"job_id": job_id}
            if log_failed_parser:
                extra["parser"] = running_job.parser
            logger.exception(
                "parser.worker.failed",
                extra=extra,
            )
            return

        latest_job = self._job_repository.get(job_id) or running_job
        parsed_job = latest_job.model_copy(
            update={
                "status": IngestionStatus.PARSED,
                "document_id": parse_result.content.document_id,
                "metadata": latest_job.metadata | parse_result.diagnostics.metadata,
                "updated_at": datetime.now(UTC),
            }
        )
        self._job_repository.save(parsed_job)

        completed_job = parsed_job
        if self._dispatch_service is not None:
            completed_job = self._dispatch_service.enqueue_parse_result(
                parsed_job,
                parse_result,
            )
            self._job_repository.save(completed_job)
            self._dispatch_service.notify()

        completed_fields = {
            "job_id": job_id,
            "document_id": parse_result.content.document_id,
            "page_count": parse_result.content.metadata.get("page_count"),
            "element_count": parse_result.content.metadata.get("element_count"),
            "chunk_count": parse_result.diagnostics.chunk_count,
            "rag_record_count": len(parse_result.content.rag_records),
            "duration_ms": parse_result.diagnostics.duration_ms,
        }
        if log_completed_context:
            completed_fields.update(
                {
                    "parser": running_job.parser,
                    "pipeline": completed_job.metadata.get("pipeline") or requested.pipeline,
                    "input_format": completed_job.metadata.get("input_format"),
                    "status": completed_job.status,
                }
            )
        log_stage("parser.worker.completed", **completed_fields)

    def _fail_job(
        self,
        job: IngestionJob,
        *,
        error: str,
        error_type: str,
        exc: Exception | None = None,
        log_parser: bool = False,
    ) -> None:
        failed_job = job.model_copy(
            update={
                "status": IngestionStatus.FAILED,
                "error": error,
                "metadata": job.metadata
                | build_error_metadata(
                    error_type=error_type,
                    exc=exc,
                    include_validation_error=self._include_validation_error_metadata,
                ),
                "updated_at": datetime.now(UTC),
                "completed_at": datetime.now(UTC),
            }
        )
        self._job_repository.save(failed_job)
        failed_fields = {
            "job_id": job.job_id,
            "error_type": error_type,
            "error": error,
        }
        if log_parser:
            failed_fields["parser"] = job.parser
        log_stage("parser.worker.failed", **failed_fields)

    @staticmethod
    def _requested_parse_options(job: IngestionJob) -> RequestedParseOptions:
        return RequestedParseOptions(
            pipeline=job.metadata.get("requested_pipeline"),
            chunking_enabled=job.metadata.get("requested_chunking_enabled"),
            chunking_strategy=job.metadata.get("requested_chunking_strategy"),
            ocr_languages=ocr_languages_from_metadata(job.metadata),
            include_html=bool(job.metadata.get("requested_include_html")),
        )

    @staticmethod
    def _optional_bool(value: object) -> bool | None:
        return bool(value) if value is not None else None

    @staticmethod
    def _optional_string(value: object) -> str | None:
        return str(value) if value is not None else None
