from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from ingest_orquestator_server.application.ports.ingestion_job_repository import (
    IngestionJobRepository,
)
from ingest_orquestator_server.application.ports.upload_file import UploadFileLike
from ingest_orquestator_server.application.ports.upload_storage import UploadStorage
from ingest_orquestator_server.application.services.document_parse_service import (
    DocumentParseService,
)
from ingest_orquestator_server.application.services.ingestion_job_metadata import (
    build_error_metadata,
    build_request_metadata,
)
from ingest_orquestator_server.application.services.job_parse_coordinator import (
    JobParseCoordinator,
)
from ingest_orquestator_server.application.services.stage_logger import log_stage
from ingest_orquestator_server.application.validation.parser_request_validator import (
    ParserRequestValidator,
    build_default_parser_request_validator,
)
from ingest_orquestator_server.application.validation.upload_validator import UploadValidator
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.models.ingest_batch_response import IngestBatchResponse
from ingest_orquestator_server.models.ingest_response import IngestResponse
from ingest_orquestator_server.models.ingestion_job import IngestionJob
from ingest_orquestator_server.models.ingestion_status import IngestionStatus

if TYPE_CHECKING:
    from ingest_orquestator_server.application.ports.job_queue import ParserJobQueue
    from ingest_orquestator_server.application.services.embedding_dispatch_service import (
        EmbeddingDispatchService,
    )
    from ingest_orquestator_server.application.services.parser_worker_service import (
        ParserWorkerService,
    )


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
        parser_job_queue: ParserJobQueue | None = None,
        parser_request_validator: ParserRequestValidator | None = None,
    ) -> None:
        self._settings = settings
        self._upload_storage = upload_storage
        self._job_repository = job_repository
        self._upload_validator = upload_validator
        self._parser_request_validator = (
            parser_request_validator or build_default_parser_request_validator(settings)
        )
        self._embedding_dispatch_service = embedding_dispatch_service
        self._parser_worker_service = parser_worker_service
        self._parser_job_queue = parser_job_queue
        self._parse_coordinator = JobParseCoordinator(
            settings=settings,
            document_parse_service=document_parse_service,
            job_repository=job_repository,
            dispatch_service=embedding_dispatch_service,
            include_validation_error_metadata=True,
        )

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
        self._parser_request_validator.validate(
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
        metadata = build_request_metadata(
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
        try:
            if self._parser_job_queue is not None:
                self._parser_job_queue.enqueue_parser_job(job_id)
            elif self._parser_worker_service is not None:
                self._parser_worker_service.submit_job(job_id)
        except Exception as exc:
            failed_job = job.model_copy(
                update={
                    "status": IngestionStatus.RETRYABLE_FAILURE,
                    "metadata": job.metadata
                    | build_error_metadata(error_type=type(exc).__name__, exc=exc),
                    "error": str(exc),
                    "updated_at": datetime.now(UTC),
                }
            )
            self._job_repository.save(failed_job)
            log_stage(
                "parser.queue.failed",
                job_id=job_id,
                parser=parser_name,
                pipeline=pipeline,
                error_type=type(exc).__name__,
                error=str(exc),
            )
            return self._ingest_response(
                job_id=job_id,
                status=IngestionStatus.RETRYABLE_FAILURE,
                parser=parser_name,
                source_file_name=upload.filename,
                input_path=upload_path,
                metadata=failed_job.metadata,
                error=str(exc),
            )
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
        self._parse_coordinator.process_job(
            job_id=job_id,
            preserve_existing_started_at=False,
            log_parse_started=True,
            log_started_input_path=False,
            log_completed_context=True,
            log_failed_parser=True,
        )

    def process_embedding_queue(self) -> None:
        if self._embedding_dispatch_service is not None:
            log_stage("dispatch.queue.drain.started")
            self._embedding_dispatch_service.drain()
            log_stage("dispatch.queue.drain.completed")

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
        metadata = build_request_metadata(
            pipeline=pipeline,
            chunking_enabled=chunking_enabled,
            chunking_strategy=chunking_strategy,
        ) | {
            "source_file_name": upload.filename,
            **build_error_metadata(
                error_type=type(error).__name__,
                exc=error,
                include_validation_error=True,
            ),
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
