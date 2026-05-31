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
from ingest_orquestator_server.application.services.embedding_dispatch_service import (
    EmbeddingDispatchService,
)
from ingest_orquestator_server.application.services.embedding_queue_service import (
    EmbeddingQueueService,
)
from ingest_orquestator_server.application.services.file_ingestion_service import (
    FileIngestionService,
)
from ingest_orquestator_server.application.services.job_query_service import JobQueryService
from ingest_orquestator_server.application.services.output_retrieval_service import (
    OutputRetrievalService,
)
from ingest_orquestator_server.application.services.parser_worker_service import (
    ParserWorkerService,
)
from ingest_orquestator_server.application.services.storage_cleanup_service import (
    StorageCleanupService,
)
from ingest_orquestator_server.application.validation.upload_validator import UploadValidator
from ingest_orquestator_server.config.settings import Settings, get_settings
from ingest_orquestator_server.infrastructure.docling.docling_engine import (
    DoclingConversionScheduler,
    DoclingEngineRegistry,
)
from ingest_orquestator_server.infrastructure.elastic.elastic_embedding_dispatcher import (
    ElasticEmbeddingDispatcher,
)
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

_embedding_queue_service: EmbeddingQueueService | None = None
_embedding_queue_key: tuple[int, int, int | None] | None = None
_embedding_dispatch_service: EmbeddingDispatchService | None = None
_embedding_dispatch_key: tuple[str, int, int, int | None] | None = None
_parser_worker_service: ParserWorkerService | None = None
_parser_worker_key: tuple[int] | None = None
_docling_engine_registry: DoclingEngineRegistry | None = None
_docling_engine_registry_key: str | None = None
_docling_conversion_scheduler: DoclingConversionScheduler | None = None
_docling_conversion_scheduler_key: str | None = None


def get_docling_engine_registry(
    settings: SettingsDependency,
) -> DoclingEngineRegistry:
    global _docling_engine_registry, _docling_engine_registry_key
    key = _settings_dependency_key(settings)
    if _docling_engine_registry is None or _docling_engine_registry_key != key:
        _docling_engine_registry = DoclingEngineRegistry(settings=settings)
        _docling_engine_registry_key = key
    return _docling_engine_registry


def get_docling_conversion_scheduler(
    registry: Annotated[
        DoclingEngineRegistry,
        Depends(get_docling_engine_registry),
    ],
) -> DoclingConversionScheduler:
    global _docling_conversion_scheduler, _docling_conversion_scheduler_key
    scheduler_key = str(id(registry))
    if _docling_conversion_scheduler is None or _docling_conversion_scheduler_key != scheduler_key:
        _docling_conversion_scheduler = DoclingConversionScheduler(
            engine_registry=registry,
        )
        _docling_conversion_scheduler_key = scheduler_key
    return _docling_conversion_scheduler


def get_parser_registry(
    settings: SettingsDependency,
    docling_conversion_scheduler: Annotated[
        DoclingConversionScheduler,
        Depends(get_docling_conversion_scheduler),
    ],
) -> ParserRegistry:
    return build_parser_registry(
        settings,
        docling_conversion_scheduler=docling_conversion_scheduler,
    )


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
        embedding_output_enabled=settings.embedding_output_enabled,
    )


def get_embedding_queue_service(settings: SettingsDependency) -> EmbeddingQueueService:
    global _embedding_queue_key, _embedding_queue_service
    key = (
        settings.dispatch_max_bulk_size,
        settings.dispatch_queue_max_size,
        settings.dispatch_queue_max_payload_bytes,
    )
    if _embedding_queue_service is None or _embedding_queue_key != key:
        _embedding_queue_service = EmbeddingQueueService(
            max_bulk_size=settings.dispatch_max_bulk_size,
            max_size=settings.dispatch_queue_max_size,
            max_payload_bytes=settings.dispatch_queue_max_payload_bytes,
        )
        _embedding_queue_key = key
    return _embedding_queue_service


def get_embedding_dispatch_service(
    settings: SettingsDependency,
    queue_service: Annotated[
        EmbeddingQueueService,
        Depends(get_embedding_queue_service),
    ],
    job_repository: Annotated[
        SqliteIngestionJobRepository,
        Depends(get_job_repository),
    ],
) -> EmbeddingDispatchService:
    global _embedding_dispatch_key, _embedding_dispatch_service
    key = (
        settings.dispatch_sink_mode,
        settings.dispatch_max_bulk_size,
        settings.dispatch_queue_max_size,
        settings.dispatch_queue_max_payload_bytes,
    )
    if _embedding_dispatch_service is None or _embedding_dispatch_key != key:
        _embedding_dispatch_service = EmbeddingDispatchService(
            settings=settings,
            queue_service=queue_service,
            dispatcher=ElasticEmbeddingDispatcher(settings),
            job_repository=job_repository,
            output_writer=LocalParseOutputWriter(),
        )
        _embedding_dispatch_key = key
    _embedding_dispatch_service.start()
    return _embedding_dispatch_service


def get_parser_worker_service(
    settings: SettingsDependency,
    document_parse_service: Annotated[
        DocumentParseService,
        Depends(get_document_parse_service),
    ],
    job_repository: Annotated[
        SqliteIngestionJobRepository,
        Depends(get_job_repository),
    ],
    dispatch_service: Annotated[
        EmbeddingDispatchService,
        Depends(get_embedding_dispatch_service),
    ],
) -> ParserWorkerService:
    global _parser_worker_key, _parser_worker_service
    key = (settings.parser_worker_count,)
    if _parser_worker_service is None or _parser_worker_key != key:
        _parser_worker_service = ParserWorkerService(
            settings=settings,
            document_parse_service=document_parse_service,
            job_repository=job_repository,
            dispatch_service=dispatch_service,
        )
        _parser_worker_service.recover_active_jobs()
        _parser_worker_key = key
    return _parser_worker_service


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
    embedding_dispatch_service: Annotated[
        EmbeddingDispatchService,
        Depends(get_embedding_dispatch_service),
    ],
    parser_worker_service: Annotated[
        ParserWorkerService,
        Depends(get_parser_worker_service),
    ],
) -> FileIngestionService:
    return FileIngestionService(
        settings=settings,
        upload_storage=LocalUploadStorage(upload_validator=upload_validator),
        document_parse_service=document_parse_service,
        job_repository=job_repository,
        upload_validator=upload_validator,
        embedding_dispatch_service=embedding_dispatch_service,
        parser_worker_service=parser_worker_service,
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


def shutdown_background_services() -> None:
    if _parser_worker_service is not None:
        _parser_worker_service.shutdown()
    if _embedding_dispatch_service is not None:
        _embedding_dispatch_service.stop()


def warmup_docling_engines(settings: Settings | None = None) -> None:
    resolved_settings = settings or get_settings()
    if not resolved_settings.docling_engine_warmup_enabled:
        return
    registry = get_docling_engine_registry(resolved_settings)
    registry.warmup()


def _settings_dependency_key(settings: Settings) -> str:
    return settings.model_dump_json()
