from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from ingest_orquestator_server.application.exceptions import (
    UnsupportedDocumentFormatError,
    UnsupportedIngestionOptionError,
    UnsupportedPipelineError,
)
from ingest_orquestator_server.application.ports.ingestion_job_repository import (
    IngestionJobRepository,
)
from ingest_orquestator_server.application.ports.upload_file import UploadFileLike
from ingest_orquestator_server.application.ports.upload_storage import UploadStorage
from ingest_orquestator_server.application.services.document_parse_service import (
    DocumentParseService,
)
from ingest_orquestator_server.application.services.stage_logger import log_stage
from ingest_orquestator_server.application.validation.upload_validator import UploadValidator
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.models.ingest_batch_response import IngestBatchResponse
from ingest_orquestator_server.models.ingest_response import IngestResponse
from ingest_orquestator_server.models.ingestion_job import IngestionJob
from ingest_orquestator_server.models.ingestion_status import IngestionStatus

if TYPE_CHECKING:
    from ingest_orquestator_server.application.services.embedding_dispatch_service import (
        EmbeddingDispatchService,
    )
    from ingest_orquestator_server.application.services.parser_worker_service import (
        ParserWorkerService,
    )

logger = logging.getLogger(__name__)


class FileIngestionService:
    def __init__(
        self,
        *,
        settings: Settings,
        upload_storage: UploadStorage,
        document_parse_service: DocumentParseService,
        job_repository: IngestionJobRepository,
        upload_validator: UploadValidator,
        embedding_dispatch_service: EmbeddingDispatchService | None = None,
        parser_worker_service: ParserWorkerService | None = None,
    ) -> None:
        self._settings = settings
        self._upload_storage = upload_storage
        self._document_parse_service = document_parse_service
        self._job_repository = job_repository
        self._upload_validator = upload_validator
        self._embedding_dispatch_service = embedding_dispatch_service
        self._parser_worker_service = parser_worker_service

    async def ingest_upload(
        self,
        *,
        upload: UploadFileLike,
        parser_name: str,
        include_document: bool,
        pipeline: str | None = None,
        chunking_enabled: bool | None = None,
        chunking_strategy: str | None = None,
    ) -> IngestResponse:
        return await self.enqueue_upload(
            upload=upload,
            parser_name=parser_name,
            pipeline=pipeline,
            chunking_enabled=chunking_enabled,
            chunking_strategy=chunking_strategy,
        )

    async def enqueue_upload(
        self,
        *,
        upload: UploadFileLike,
        parser_name: str,
        pipeline: str | None = None,
        chunking_enabled: bool | None = None,
        chunking_strategy: str | None = None,
    ) -> IngestResponse:
        self._upload_validator.validate_metadata(upload)
        self._validate_parser_request(
            filename=upload.filename or "",
            parser_name=parser_name,
            pipeline=pipeline,
            chunking_strategy=chunking_strategy,
        )
        job_id = str(uuid4())
        log_stage(
            "ingestion.upload.queued",
            job_id=job_id,
            parser=parser_name,
            pipeline=pipeline,
            filename=upload.filename,
        )
        upload_path = await self._upload_storage.save(
            upload,
            self._settings.uploads_dir,
            job_id=job_id,
        )
        metadata = self._request_metadata(
            pipeline=pipeline,
            chunking_enabled=chunking_enabled,
            chunking_strategy=chunking_strategy,
        )
        job = IngestionJob(
            job_id=job_id,
            status=IngestionStatus.PARSER_QUEUED,
            parser=parser_name,
            source_file_name=upload.filename,
            input_path=upload_path,
            metadata=metadata,
        )
        self._job_repository.save(job)
        log_stage(
            "ingestion.upload.stored",
            job_id=job_id,
            parser=parser_name,
            pipeline=pipeline,
            source_file_name=upload.filename,
            input_path=upload_path,
        )
        if self._parser_worker_service is not None:
            self._parser_worker_service.submit_job(job_id)
        return self._ingest_response(
            job_id=job_id,
            status=IngestionStatus.PARSER_QUEUED,
            parser=parser_name,
            source_file_name=upload.filename,
            input_path=upload_path,
            metadata=metadata,
        )

    async def enqueue_uploads(
        self,
        *,
        uploads: list[UploadFileLike],
        parser_name: str,
        pipeline: str | None = None,
        chunking_enabled: bool | None = None,
        chunking_strategy: str | None = None,
    ) -> IngestBatchResponse:
        jobs: list[IngestResponse] = []
        failed: list[IngestResponse] = []
        for upload in uploads:
            try:
                jobs.append(
                    await self.enqueue_upload(
                        upload=upload,
                        parser_name=parser_name,
                        pipeline=pipeline,
                        chunking_enabled=chunking_enabled,
                        chunking_strategy=chunking_strategy,
                    )
                )
            except Exception as exc:
                failed_job = self._save_rejected_batch_job(
                    upload=upload,
                    parser_name=parser_name,
                    pipeline=pipeline,
                    chunking_enabled=chunking_enabled,
                    chunking_strategy=chunking_strategy,
                    error=exc,
                )
                failed.append(
                    self._ingest_response(
                        job_id=failed_job.job_id,
                        status=IngestionStatus.FAILED,
                        parser=parser_name,
                        source_file_name=upload.filename,
                        metadata=failed_job.metadata,
                        error=str(exc),
                    )
                )
        return IngestBatchResponse(jobs=jobs, failed=failed)

    def process_queued_job(self, job_id: str) -> None:
        if self._parser_worker_service is not None:
            self._parser_worker_service.process_job(job_id)
            return
        job = self._job_repository.get(job_id)
        if job is None:
            return

        pipeline = job.metadata.get("requested_pipeline")
        chunking_enabled = job.metadata.get("requested_chunking_enabled")
        chunking_strategy = job.metadata.get("requested_chunking_strategy")
        running_job = job.model_copy(
            update={
                "status": IngestionStatus.PARSING,
                "started_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            }
        )
        self._job_repository.save(running_job)
        log_stage(
            "parser.worker.started",
            job_id=job_id,
            parser=running_job.parser,
            pipeline=pipeline,
        )

        try:
            if running_job.input_path is None:
                raise FileNotFoundError("Queued job has no input path.")
            log_stage(
                "parser.worker.parse.started",
                job_id=job_id,
                parser=running_job.parser,
                pipeline=pipeline,
                input_path=running_job.input_path,
            )
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
            failed_job = running_job.model_copy(
                update={
                    "status": IngestionStatus.FAILED,
                    "error": str(exc),
                    "metadata": running_job.metadata | self._error_metadata(exc),
                    "updated_at": datetime.now(UTC),
                    "completed_at": datetime.now(UTC),
                }
            )
            self._job_repository.save(failed_job)
            log_stage(
                "parser.worker.failed",
                job_id=job_id,
                parser=running_job.parser,
                error_type=type(exc).__name__,
                error=str(exc),
            )
            logger.exception(
                "parser.worker.failed",
                extra={"job_id": job_id, "parser": running_job.parser},
            )
            return

        completed_metadata = running_job.metadata | parse_result.diagnostics.metadata
        completed_job = running_job.model_copy(
            update={
                "status": IngestionStatus.PARSED,
                "document_id": parse_result.parse_output.document.document_id,
                "metadata": completed_metadata,
                "updated_at": datetime.now(UTC),
            }
        )
        self._job_repository.save(completed_job)
        if self._embedding_dispatch_service is not None:
            completed_job = self._embedding_dispatch_service.enqueue_parse_result(
                completed_job,
                parse_result,
            )
            self._job_repository.save(completed_job)
            self._embedding_dispatch_service.notify()
        log_stage(
            "parser.worker.completed",
            job_id=job_id,
            document_id=parse_result.parse_output.document.document_id,
            parser=running_job.parser,
            pipeline=completed_job.metadata.get("pipeline") or pipeline,
            input_format=completed_job.metadata.get("input_format"),
            page_count=parse_result.parse_output.document.page_count,
            element_count=len(parse_result.parse_output.document.elements),
            chunk_count=len(parse_result.chunks),
            embedding_record_count=len(parse_result.embedding_records),
            duration_ms=parse_result.diagnostics.duration_ms,
            status=completed_job.status,
        )

    def process_embedding_queue(self) -> None:
        if self._embedding_dispatch_service is not None:
            log_stage("dispatch.queue.drain.started")
            self._embedding_dispatch_service.drain()
            log_stage("dispatch.queue.drain.completed")

    @staticmethod
    def _error_metadata(exc: Exception) -> dict[str, str]:
        metadata = {"error_type": type(exc).__name__}
        if isinstance(
            exc,
            UnsupportedDocumentFormatError
            | UnsupportedPipelineError
            | UnsupportedIngestionOptionError,
        ):
            metadata["validation_error"] = "true"
        return metadata

    def _save_rejected_batch_job(
        self,
        *,
        upload: UploadFileLike,
        parser_name: str,
        pipeline: str | None,
        chunking_enabled: bool | None,
        chunking_strategy: str | None,
        error: Exception,
    ) -> IngestionJob:
        job_id = str(uuid4())
        now = datetime.now(UTC)
        metadata = self._request_metadata(
            pipeline=pipeline,
            chunking_enabled=chunking_enabled,
            chunking_strategy=chunking_strategy,
        ) | {
            "source_file_name": upload.filename,
            **self._error_metadata(error),
        }
        job = IngestionJob(
            job_id=job_id,
            status=IngestionStatus.FAILED,
            parser=parser_name,
            source_file_name=upload.filename,
            metadata=metadata,
            error=str(error),
            created_at=now,
            updated_at=now,
            completed_at=now,
        )
        self._job_repository.save(job)
        log_stage(
            "ingestion.upload.rejected",
            job_id=job_id,
            parser=parser_name,
            pipeline=pipeline,
            source_file_name=upload.filename,
            error_type=type(error).__name__,
            error=str(error),
        )
        return job

    @staticmethod
    def _ingest_response(
        *,
        job_id: str,
        status: IngestionStatus,
        parser: str,
        metadata: dict[str, object],
        source_file_name: str | None = None,
        input_path: Path | None = None,
        error: str | None = None,
    ) -> IngestResponse:
        return IngestResponse(
            job_id=job_id,
            status=status,
            parser=parser,
            source_file_name=source_file_name,
            input_path=input_path,
            metadata=metadata,
            error=error,
            status_url=f"/v1/ingest/jobs/{job_id}",
            outputs_url=f"/v1/ingest/jobs/{job_id}/outputs",
        )

    @staticmethod
    def _request_metadata(
        *,
        pipeline: str | None,
        chunking_enabled: bool | None,
        chunking_strategy: str | None,
    ) -> dict[str, object]:
        metadata: dict[str, object] = {}
        if pipeline is not None:
            metadata["requested_pipeline"] = pipeline
        if chunking_enabled is not None:
            metadata["requested_chunking_enabled"] = chunking_enabled
        if chunking_strategy is not None:
            metadata["requested_chunking_strategy"] = chunking_strategy
        return metadata

    def _validate_parser_request(
        self,
        *,
        filename: str,
        parser_name: str,
        pipeline: str | None,
        chunking_strategy: str | None = None,
    ) -> None:
        if parser_name != "docling":
            return

        from ingest_orquestator_server.config.chunking import validate_chunking_strategy
        from ingest_orquestator_server.infrastructure.docling.docling_formats import (
            detect_input_format,
            resolve_pipeline_mode,
            validate_allowed_format,
        )

        input_format = detect_input_format(Path(filename))
        validate_allowed_format(input_format, self._settings.docling_allowed_formats)
        resolve_pipeline_mode(pipeline or self._settings.docling_pipeline, input_format)
        if chunking_strategy is not None:
            validate_chunking_strategy(chunking_strategy)
