from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
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
from ingest_orquestator_server.application.validation.upload_validator import UploadValidator
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.models.ingest_response import IngestResponse
from ingest_orquestator_server.models.ingestion_job import IngestionJob
from ingest_orquestator_server.models.ingestion_status import IngestionStatus

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
    ) -> None:
        self._settings = settings
        self._upload_storage = upload_storage
        self._document_parse_service = document_parse_service
        self._job_repository = job_repository
        self._upload_validator = upload_validator

    async def ingest_upload(
        self,
        *,
        upload: UploadFileLike,
        parser_name: str,
        include_document: bool,
        pipeline: str | None = None,
        profile: str | None = None,
        chunking_enabled: bool | None = None,
        chunking_strategy: str | None = None,
    ) -> IngestResponse:
        self._upload_validator.validate_metadata(upload)
        self._validate_parser_request(
            filename=upload.filename or "",
            parser_name=parser_name,
            pipeline=pipeline,
            profile=profile,
            chunking_strategy=chunking_strategy,
        )
        job_id = str(uuid4())
        logger.info(
            "ingestion.upload.received",
            extra={
                "job_id": job_id,
                "parser": parser_name,
                "pipeline": pipeline,
                "profile": profile,
                "filename": upload.filename,
            },
        )
        upload_path = await self._upload_storage.save(
            upload,
            self._settings.uploads_dir,
            job_id=job_id,
        )

        job = IngestionJob(
            job_id=job_id,
            status=IngestionStatus.RUNNING,
            parser=parser_name,
            source_file_name=upload.filename,
            input_path=upload_path,
            metadata=self._request_metadata(
                pipeline=pipeline,
                profile=profile,
                chunking_enabled=chunking_enabled,
                chunking_strategy=chunking_strategy,
            ),
            started_at=datetime.now(UTC),
        )
        self._job_repository.save(job)

        try:
            logger.info(
                "ingestion.parse.started",
                extra={"job_id": job_id, "parser": parser_name, "pipeline": pipeline},
            )
            parse_result = self._document_parse_service.parse_file(
                file_path=upload_path,
                parser_name=parser_name,
                output_root=self._settings.outputs_dir,
                document_id=job_id,
                pipeline=pipeline,
                profile=profile,
                chunking_enabled=chunking_enabled,
                chunking_strategy=chunking_strategy,
            )
        except Exception as exc:
            failed_job = job.model_copy(
                update={
                    "status": IngestionStatus.FAILED,
                    "error": str(exc),
                    "metadata": job.metadata | self._error_metadata(exc),
                    "updated_at": datetime.now(UTC),
                    "completed_at": datetime.now(UTC),
                }
            )
            self._job_repository.save(failed_job)
            logger.exception(
                "ingestion.parse.failed",
                extra={"job_id": job_id, "parser": parser_name},
            )
            raise

        completed_metadata = job.metadata | parse_result.diagnostics.metadata
        completed_job = job.model_copy(
            update={
                "status": IngestionStatus.COMPLETED,
                "document_id": parse_result.parse_output.document.document_id,
                "outputs": parse_result.outputs,
                "metadata": completed_metadata,
                "updated_at": datetime.now(UTC),
                "completed_at": datetime.now(UTC),
            }
        )
        self._job_repository.save(completed_job)
        logger.info(
            "ingestion.parse.completed",
            extra={
                "job_id": job_id,
                "parser": parser_name,
                "duration_ms": parse_result.diagnostics.duration_ms,
                "output_dir": str(parse_result.outputs.output_dir),
            },
        )

        return IngestResponse(
            job_id=job_id,
            status=IngestionStatus.COMPLETED,
            parser=parser_name,
            document_id=parse_result.parse_output.document.document_id,
            input_path=upload_path,
            outputs=parse_result.outputs,
            metadata=completed_metadata,
            document=parse_result.parse_output.document if include_document else None,
            chunks=parse_result.chunks if include_document else None,
        )

    async def enqueue_upload(
        self,
        *,
        upload: UploadFileLike,
        parser_name: str,
        pipeline: str | None = None,
        profile: str | None = None,
        chunking_enabled: bool | None = None,
        chunking_strategy: str | None = None,
    ) -> IngestResponse:
        self._upload_validator.validate_metadata(upload)
        self._validate_parser_request(
            filename=upload.filename or "",
            parser_name=parser_name,
            pipeline=pipeline,
            profile=profile,
            chunking_strategy=chunking_strategy,
        )
        job_id = str(uuid4())
        logger.info(
            "ingestion.upload.queued",
            extra={
                "job_id": job_id,
                "parser": parser_name,
                "pipeline": pipeline,
                "profile": profile,
                "filename": upload.filename,
            },
        )
        upload_path = await self._upload_storage.save(
            upload,
            self._settings.uploads_dir,
            job_id=job_id,
        )
        metadata = self._request_metadata(
            pipeline=pipeline,
            profile=profile,
            chunking_enabled=chunking_enabled,
            chunking_strategy=chunking_strategy,
        )
        job = IngestionJob(
            job_id=job_id,
            status=IngestionStatus.QUEUED,
            parser=parser_name,
            source_file_name=upload.filename,
            input_path=upload_path,
            metadata=metadata,
        )
        self._job_repository.save(job)
        return IngestResponse(
            job_id=job_id,
            status=IngestionStatus.QUEUED,
            parser=parser_name,
            input_path=upload_path,
            metadata=metadata,
        )

    def process_queued_job(self, job_id: str) -> None:
        job = self._job_repository.get(job_id)
        if job is None:
            return

        pipeline = job.metadata.get("requested_pipeline")
        profile = job.metadata.get("requested_profile")
        chunking_enabled = job.metadata.get("requested_chunking_enabled")
        chunking_strategy = job.metadata.get("requested_chunking_strategy")
        running_job = job.model_copy(
            update={
                "status": IngestionStatus.RUNNING,
                "started_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            }
        )
        self._job_repository.save(running_job)

        try:
            if running_job.input_path is None:
                raise FileNotFoundError("Queued job has no input path.")
            logger.info(
                "ingestion.background.parse.started",
                extra={"job_id": job_id, "parser": running_job.parser, "pipeline": pipeline},
            )
            parse_result = self._document_parse_service.parse_file(
                file_path=running_job.input_path,
                parser_name=running_job.parser,
                output_root=self._settings.outputs_dir,
                document_id=job_id,
                pipeline=str(pipeline) if pipeline is not None else None,
                profile=str(profile) if profile is not None else None,
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
            logger.exception(
                "ingestion.background.parse.failed",
                extra={"job_id": job_id, "parser": running_job.parser},
            )
            return

        completed_metadata = running_job.metadata | parse_result.diagnostics.metadata
        completed_job = running_job.model_copy(
            update={
                "status": IngestionStatus.COMPLETED,
                "document_id": parse_result.parse_output.document.document_id,
                "outputs": parse_result.outputs,
                "metadata": completed_metadata,
                "updated_at": datetime.now(UTC),
                "completed_at": datetime.now(UTC),
            }
        )
        self._job_repository.save(completed_job)
        logger.info(
            "ingestion.background.parse.completed",
            extra={
                "job_id": job_id,
                "parser": running_job.parser,
                "duration_ms": parse_result.diagnostics.duration_ms,
                "output_dir": str(parse_result.outputs.output_dir),
            },
        )

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

    @staticmethod
    def _request_metadata(
        *,
        pipeline: str | None,
        profile: str | None,
        chunking_enabled: bool | None,
        chunking_strategy: str | None,
    ) -> dict[str, object]:
        metadata: dict[str, object] = {}
        if pipeline is not None:
            metadata["requested_pipeline"] = pipeline
        if profile is not None:
            metadata["requested_profile"] = profile
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
        profile: str | None = None,
        chunking_strategy: str | None = None,
    ) -> None:
        if parser_name != "docling":
            return

        from ingest_orquestator_server.config.profiles import (
            resolve_profile_settings,
            validate_chunking_strategy,
            validate_profile_name,
        )
        from ingest_orquestator_server.infrastructure.docling.docling_formats import (
            detect_input_format,
            resolve_pipeline_mode,
            validate_allowed_format,
        )

        input_format = detect_input_format(Path(filename))
        validate_allowed_format(input_format, self._settings.docling_allowed_formats)
        request_settings = self._settings
        if profile is not None:
            request_settings = resolve_profile_settings(self._settings, profile=profile)
        resolve_pipeline_mode(pipeline or request_settings.docling_pipeline, input_format)
        if profile is not None:
            validate_profile_name(profile)
        if chunking_strategy is not None:
            validate_chunking_strategy(chunking_strategy)
