from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from ingest_orquestator_server.application.parser_registry import ParserRegistry
from ingest_orquestator_server.application.services.document_chunking_service import (
    DocumentChunkingService,
)
from ingest_orquestator_server.application.services.document_parse_service import (
    DocumentParseService,
)
from ingest_orquestator_server.application.services.file_ingestion_service import (
    FileIngestionService,
)
from ingest_orquestator_server.application.services.job_query_service import JobQueryService
from ingest_orquestator_server.application.services.output_retrieval_service import (
    OutputRetrievalService,
)
from ingest_orquestator_server.application.services.storage_cleanup_service import (
    StorageCleanupService,
)
from ingest_orquestator_server.application.validation.upload_validator import UploadValidator
from ingest_orquestator_server.config.settings import Settings, get_settings
from ingest_orquestator_server.infrastructure.filesystem.local_parse_output_writer import (
    LocalParseOutputWriter,
)
from ingest_orquestator_server.infrastructure.filesystem.local_upload_storage import (
    LocalUploadStorage,
)
from ingest_orquestator_server.infrastructure.parser.parser_registry_factory import (
    build_parser_registry,
)
from ingest_orquestator_server.infrastructure.sqlite.sqlite_ingestion_job_repository import (
    SqliteIngestionJobRepository,
)

SettingsDependency = Annotated[Settings, Depends(get_settings)]


def get_parser_registry(settings: SettingsDependency) -> ParserRegistry:
    return build_parser_registry(settings)


def get_job_repository(
    settings: SettingsDependency,
) -> SqliteIngestionJobRepository:
    return SqliteIngestionJobRepository(settings.jobs_db_path)


def get_upload_validator(settings: SettingsDependency) -> UploadValidator:
    return UploadValidator(settings)


def get_document_parse_service(
    settings: SettingsDependency,
    parser_registry: Annotated[ParserRegistry, Depends(get_parser_registry)],
) -> DocumentParseService:
    return DocumentParseService(
        parser_registry=parser_registry,
        output_writer=LocalParseOutputWriter(),
        chunking_service=DocumentChunkingService(settings),
    )


def get_file_ingestion_service(
    settings: SettingsDependency,
    document_parse_service: Annotated[
        DocumentParseService,
        Depends(get_document_parse_service),
    ],
    job_repository: Annotated[
        SqliteIngestionJobRepository,
        Depends(get_job_repository),
    ],
    upload_validator: Annotated[UploadValidator, Depends(get_upload_validator)],
) -> FileIngestionService:
    return FileIngestionService(
        settings=settings,
        upload_storage=LocalUploadStorage(upload_validator=upload_validator),
        document_parse_service=document_parse_service,
        job_repository=job_repository,
        upload_validator=upload_validator,
    )


def get_job_query_service(
    job_repository: Annotated[SqliteIngestionJobRepository, Depends(get_job_repository)],
) -> JobQueryService:
    return JobQueryService(job_repository)


def get_output_retrieval_service(
    job_repository: Annotated[SqliteIngestionJobRepository, Depends(get_job_repository)],
) -> OutputRetrievalService:
    return OutputRetrievalService(job_repository)


def get_storage_cleanup_service(
    settings: SettingsDependency,
    job_repository: Annotated[SqliteIngestionJobRepository, Depends(get_job_repository)],
) -> StorageCleanupService:
    return StorageCleanupService(settings=settings, job_repository=job_repository)
