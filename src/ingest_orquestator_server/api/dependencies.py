from __future__ import annotations

from functools import partial
from typing import Annotated

from fastapi import Depends

from ingest_orquestator_server.application.parser_registry import ParserRegistry
from ingest_orquestator_server.application.ports.job_queue import JobQueuePublisher
from ingest_orquestator_server.application.services.document_parse_service import (
    DocumentParseService,
)
from ingest_orquestator_server.application.services.file_ingestion_service import (
    FileIngestionService,
)
from ingest_orquestator_server.application.services.ingestor_settings_service import (
    IngestorSettingsService,
)
from ingest_orquestator_server.application.services.job_query_service import JobQueryService
from ingest_orquestator_server.application.services.job_removal_service import (
    JobRemovalService,
)
from ingest_orquestator_server.application.services.output_retrieval_service import (
    OutputRetrievalService,
)
from ingest_orquestator_server.application.services.parsed_document_dispatch_queue_service import (
    ParsedDocumentDispatchQueueService,
)
from ingest_orquestator_server.application.services.parsed_document_dispatch_service import (
    ParsedDocumentDispatchService,
)
from ingest_orquestator_server.application.services.parser_worker_service import (
    ParserWorkerService,
)
from ingest_orquestator_server.application.services.queue_metrics_service import (
    QueueMetricsService,
)
from ingest_orquestator_server.application.services.storage_cleanup_service import (
    StorageCleanupService,
)
from ingest_orquestator_server.application.validation.parser_request_validator import (
    ParserRequestValidator,
)
from ingest_orquestator_server.application.validation.upload_validator import UploadValidator
from ingest_orquestator_server.config.settings import Settings, get_settings
from ingest_orquestator_server.infrastructure.docling.docling_engine import (
    DoclingConversionScheduler,
    DoclingEngineRegistry,
)
from ingest_orquestator_server.infrastructure.elastic.elastic_chunk_index_dispatch_sink import (
    ElasticChunkIndexDispatchSink,
)
from ingest_orquestator_server.infrastructure.filesystem.local_parse_output_writer import (
    LocalParseOutputWriter,
)
from ingest_orquestator_server.infrastructure.filesystem.local_upload_storage import (
    LocalUploadStorage,
)
from ingest_orquestator_server.infrastructure.parser.parser_chunking_factory import (
    build_parser_chunking_service,
)
from ingest_orquestator_server.infrastructure.parser.parser_registry_factory import (
    build_parser_registry,
)
from ingest_orquestator_server.infrastructure.parser.parser_request_validator_factory import (
    build_parser_request_validator,
)
from ingest_orquestator_server.infrastructure.queue import DramatiqJobQueuePublisher
from ingest_orquestator_server.infrastructure.sqlite.sqlite_ingestion_job_repository import (
    SqliteIngestionJobRepository,
)
from ingest_orquestator_server.infrastructure.sqlite.sqlite_ingestor_settings_repository import (
    SqliteIngestorSettingsRepository,
)

BaseSettingsDependency = Annotated[Settings, Depends(get_settings)]


def get_ingestor_settings_repository(
    settings: BaseSettingsDependency,
) -> SqliteIngestorSettingsRepository:
    return SqliteIngestorSettingsRepository(settings.jobs_db_path)


def get_ingestor_settings_service(
    settings: BaseSettingsDependency,
    repository: Annotated[
        SqliteIngestorSettingsRepository,
        Depends(get_ingestor_settings_repository),
    ],
) -> IngestorSettingsService:
    return IngestorSettingsService(base_settings=settings, repository=repository)


def get_effective_settings(
    service: Annotated[IngestorSettingsService, Depends(get_ingestor_settings_service)],
) -> Settings:
    return service.effective_settings()


SettingsDependency = Annotated[Settings, Depends(get_effective_settings)]

_parsed_document_dispatch_queue_service: ParsedDocumentDispatchQueueService | None = None
_parsed_document_dispatch_queue_key: tuple[int, int, int | None] | None = None
_parsed_document_dispatch_service: ParsedDocumentDispatchService | None = None
_parsed_document_dispatch_key: (
    tuple[str, int, int, int | None, int, str, str, str, str] | None
) = None
_parser_worker_service: ParserWorkerService | None = None
_parser_worker_key: str | None = None
_job_queue_publisher: JobQueuePublisher | None = None
_job_queue_key: tuple[str, str, str, str] | None = None
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


def get_parser_request_validator(settings: SettingsDependency) -> ParserRequestValidator:
    return build_parser_request_validator(settings)


def get_document_parse_service(
    settings: SettingsDependency,
    parser_registry: Annotated[ParserRegistry, Depends(get_parser_registry)],
) -> DocumentParseService:
    return DocumentParseService(
        parser_registry=parser_registry,
        output_writer=LocalParseOutputWriter(),
        chunking_service=build_parser_chunking_service(settings),
        embedding_output_enabled=settings.embedding_output_enabled,
    )


def get_parsed_document_dispatch_queue_service(
    settings: SettingsDependency,
) -> ParsedDocumentDispatchQueueService:
    global _parsed_document_dispatch_queue_key, _parsed_document_dispatch_queue_service
    key = (
        settings.dispatch_max_bulk_size,
        settings.dispatch_queue_max_size,
        settings.dispatch_queue_max_payload_bytes,
    )
    if (
        _parsed_document_dispatch_queue_service is None
        or _parsed_document_dispatch_queue_key != key
    ):
        _parsed_document_dispatch_queue_service = ParsedDocumentDispatchQueueService(
            max_bulk_size=settings.dispatch_max_bulk_size,
            max_size=settings.dispatch_queue_max_size,
            max_payload_bytes=settings.dispatch_queue_max_payload_bytes,
        )
        _parsed_document_dispatch_queue_key = key
    return _parsed_document_dispatch_queue_service


def get_job_queue_publisher(settings: SettingsDependency) -> JobQueuePublisher | None:
    global _job_queue_key, _job_queue_publisher
    if settings.queue_backend == "local":
        return None
    key = (
        settings.queue_backend,
        settings.rabbitmq_url,
        settings.dramatiq_parser_queue_name,
        settings.dramatiq_dispatch_queue_name,
    )
    if _job_queue_publisher is None or _job_queue_key != key:
        _job_queue_publisher = DramatiqJobQueuePublisher.from_settings(settings)
        _job_queue_key = key
    return _job_queue_publisher


def get_parsed_document_dispatch_service(
    settings: SettingsDependency,
    queue_service: Annotated[
        ParsedDocumentDispatchQueueService,
        Depends(get_parsed_document_dispatch_queue_service),
    ],
    job_repository: Annotated[
        SqliteIngestionJobRepository,
        Depends(get_job_repository),
    ],
    job_queue_publisher: Annotated[
        JobQueuePublisher | None,
        Depends(get_job_queue_publisher),
    ],
) -> ParsedDocumentDispatchService:
    global _parsed_document_dispatch_key, _parsed_document_dispatch_service
    key = (
        settings.dispatch_sink_mode,
        settings.dispatch_max_bulk_size,
        settings.dispatch_queue_max_size,
        settings.dispatch_queue_max_payload_bytes,
        settings.dispatch_worker_count,
        settings.queue_backend,
        settings.rabbitmq_url,
        settings.dramatiq_parser_queue_name,
        settings.dramatiq_dispatch_queue_name,
    )
    if (
        _parsed_document_dispatch_service is None
        or _parsed_document_dispatch_key != key
    ):
        if _parsed_document_dispatch_service is not None:
            _parsed_document_dispatch_service.stop()
        _parsed_document_dispatch_service = ParsedDocumentDispatchService(
            settings=settings,
            queue_service=queue_service,
            dispatcher=ElasticChunkIndexDispatchSink(settings),
            job_repository=job_repository,
            output_writer=LocalParseOutputWriter(),
            dispatch_job_queue=job_queue_publisher,
        )
        _parsed_document_dispatch_key = key
    if settings.queue_backend == "local":
        _parsed_document_dispatch_service.start()
    return _parsed_document_dispatch_service


def get_parser_worker_service(
    settings: SettingsDependency,
    job_repository: Annotated[
        SqliteIngestionJobRepository,
        Depends(get_job_repository),
    ],
) -> ParserWorkerService:
    from ingest_orquestator_server.infrastructure.queue.dramatiq_runtime import (
        run_parser_job,
    )

    global _parser_worker_key, _parser_worker_service
    key = _settings_dependency_key(settings)
    if _parser_worker_service is None or _parser_worker_key != key:
        if _parser_worker_service is not None:
            _parser_worker_service.shutdown()
        _parser_worker_service = ParserWorkerService(
            settings=settings,
            job_repository=job_repository,
            job_runner=partial(
                run_parser_job,
                settings_data=settings.model_dump(mode="python"),
            ),
        )
        if settings.queue_backend == "local":
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
    parser_request_validator: Annotated[
        ParserRequestValidator,
        Depends(get_parser_request_validator),
    ],
    parsed_document_dispatch_service: Annotated[
        ParsedDocumentDispatchService,
        Depends(get_parsed_document_dispatch_service),
    ],
    parser_worker_service: Annotated[
        ParserWorkerService,
        Depends(get_parser_worker_service),
    ],
    job_queue_publisher: Annotated[
        JobQueuePublisher | None,
        Depends(get_job_queue_publisher),
    ],
) -> FileIngestionService:
    return FileIngestionService(
        settings=settings,
        upload_storage=LocalUploadStorage(upload_validator=upload_validator),
        document_parse_service=document_parse_service,
        job_repository=job_repository,
        upload_validator=upload_validator,
        parser_request_validator=parser_request_validator,
        parsed_document_dispatch_service=parsed_document_dispatch_service,
        parser_worker_service=parser_worker_service,
        parser_job_queue=job_queue_publisher,
    )


def get_job_query_service(
    job_repository: Annotated[SqliteIngestionJobRepository, Depends(get_job_repository)],
) -> JobQueryService:
    return JobQueryService(job_repository)


def get_job_removal_service(
    settings: SettingsDependency,
    job_repository: Annotated[SqliteIngestionJobRepository, Depends(get_job_repository)],
    queue_service: Annotated[
        ParsedDocumentDispatchQueueService,
        Depends(get_parsed_document_dispatch_queue_service),
    ],
) -> JobRemovalService:
    return JobRemovalService(
        settings=settings,
        job_repository=job_repository,
        dispatch_queue_service=queue_service,
    )


def get_queue_metrics_service(
    settings: SettingsDependency,
    job_repository: Annotated[
        SqliteIngestionJobRepository,
        Depends(get_job_repository),
    ],
    parsed_document_dispatch_service: Annotated[
        ParsedDocumentDispatchService,
        Depends(get_parsed_document_dispatch_service),
    ],
) -> QueueMetricsService:
    return QueueMetricsService(
        settings=settings,
        job_repository=job_repository,
        dispatch_service=parsed_document_dispatch_service,
    )


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
    if _parsed_document_dispatch_service is not None:
        _parsed_document_dispatch_service.stop()


def warmup_docling_engines(settings: Settings | None = None) -> None:
    resolved_settings = settings or get_settings()
    if not resolved_settings.docling_engine_warmup_enabled:
        return
    registry = get_docling_engine_registry(resolved_settings)
    registry.warmup()


def _settings_dependency_key(settings: Settings) -> str:
    return settings.model_dump_json()
