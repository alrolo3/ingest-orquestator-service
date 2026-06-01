from __future__ import annotations

from collections.abc import Mapping
from functools import partial
from typing import Any

from ingest_orquestator_server.application.services.job_parse_coordinator import (
    JobParseCoordinator,
    ParseJobResult,
)
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.queue.dramatiq_job_queue import (
    DramatiqJobQueuePublisher,
)

_configured_broker_url: str | None = None


def parser_actor_options(settings: Settings) -> dict[str, object]:
    return {
        "queue_name": settings.dramatiq_parser_queue_name,
        "time_limit": settings.dramatiq_parser_time_limit_ms,
    }


def dispatch_actor_options(settings: Settings) -> dict[str, object]:
    return {
        "queue_name": settings.dramatiq_dispatch_queue_name,
        "time_limit": settings.dramatiq_dispatch_time_limit_ms,
    }


def configure_dramatiq_broker(settings: Settings) -> None:
    global _configured_broker_url
    if _configured_broker_url == settings.rabbitmq_url:
        return
    try:
        import dramatiq
        from dramatiq.brokers.rabbitmq import RabbitmqBroker
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "dramatiq with RabbitMQ support is required when INGEST_QUEUE_BACKEND=dramatiq"
        ) from exc

    broker = RabbitmqBroker(url=settings.rabbitmq_url)
    dramatiq.set_broker(broker)
    _configured_broker_url = settings.rabbitmq_url


def build_dramatiq_publisher(settings: Settings) -> DramatiqJobQueuePublisher:
    configure_dramatiq_broker(settings)
    from ingest_orquestator_server.infrastructure.queue import dramatiq_actors

    return DramatiqJobQueuePublisher(
        parser_actor=dramatiq_actors.process_parser_job,
        dispatch_actor=dramatiq_actors.process_dispatch_job,
        parser_time_limit_ms=settings.dramatiq_parser_time_limit_ms,
        dispatch_time_limit_ms=settings.dramatiq_dispatch_time_limit_ms,
    )


def build_parser_worker_service() -> Any:
    from ingest_orquestator_server.api.dependencies import (
        get_job_repository,
    )
    from ingest_orquestator_server.application.services.parser_worker_service import (
        ParserWorkerService,
    )

    settings = effective_runtime_settings()
    job_repository = get_job_repository(settings)
    return ParserWorkerService(
        settings=settings,
        job_repository=job_repository,
        job_runner=partial(
            run_parser_job,
            settings_data=settings.model_dump(mode="python"),
        ),
    )


def effective_runtime_settings(settings: Settings | None = None) -> Settings:
    if settings is not None:
        return settings

    from ingest_orquestator_server.application.services.ingestor_settings_service import (
        IngestorSettingsService,
    )
    from ingest_orquestator_server.config.settings import get_settings
    from ingest_orquestator_server.infrastructure.sqlite import (
        SqliteIngestorSettingsRepository,
    )

    base_settings = get_settings()
    repository = SqliteIngestorSettingsRepository(base_settings.jobs_db_path)
    return IngestorSettingsService(
        base_settings=base_settings,
        repository=repository,
    ).effective_settings()


def build_parser_job_coordinator(settings: Settings | None = None) -> JobParseCoordinator:
    from ingest_orquestator_server.api.dependencies import (
        get_docling_conversion_scheduler,
        get_docling_engine_registry,
        get_document_parse_service,
        get_job_queue_publisher,
        get_job_repository,
        get_parsed_document_dispatch_queue_service,
        get_parsed_document_dispatch_service,
        get_parser_registry,
    )

    settings = effective_runtime_settings(settings)
    registry = get_docling_engine_registry(settings)
    scheduler = get_docling_conversion_scheduler(registry)
    parser_registry = get_parser_registry(settings, scheduler)
    parse_service = get_document_parse_service(settings, parser_registry)
    job_repository = get_job_repository(settings)
    dispatch_service = get_parsed_document_dispatch_service(
        settings,
        get_parsed_document_dispatch_queue_service(settings),
        job_repository,
        get_job_queue_publisher(settings),
    )
    return JobParseCoordinator(
        settings=settings,
        document_parse_service=parse_service,
        job_repository=job_repository,
        dispatch_service=dispatch_service,
    )


def run_parser_job(
    job_id: str,
    settings_data: Mapping[str, Any] | None = None,
) -> ParseJobResult:
    settings = Settings(**settings_data) if settings_data is not None else None
    coordinator = build_parser_job_coordinator(settings)
    return coordinator.process_job(
        job_id,
        preserve_existing_started_at=True,
        fail_missing_input_before_start=True,
    )


def build_dispatch_service() -> Any:
    from ingest_orquestator_server.api.dependencies import (
        get_job_repository,
        get_parsed_document_dispatch_queue_service,
        get_parsed_document_dispatch_service,
    )
    from ingest_orquestator_server.config.settings import get_settings

    settings = get_settings()
    job_repository = get_job_repository(settings)
    return get_parsed_document_dispatch_service(
        settings,
        get_parsed_document_dispatch_queue_service(settings),
        job_repository,
        None,
    )
