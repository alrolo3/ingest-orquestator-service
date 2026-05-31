from __future__ import annotations

from typing import Any

from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.queue.dramatiq_job_queue import (
    DramatiqJobQueuePublisher,
)

_configured_broker_url: str | None = None


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
    )


def build_parser_worker_service() -> Any:
    from ingest_orquestator_server.api.dependencies import (
        get_docling_conversion_scheduler,
        get_docling_engine_registry,
        get_document_parse_service,
        get_embedding_dispatch_service,
        get_embedding_queue_service,
        get_job_queue_publisher,
        get_job_repository,
        get_parser_registry,
        get_parser_worker_service,
    )
    from ingest_orquestator_server.config.settings import get_settings

    settings = get_settings()
    registry = get_docling_engine_registry(settings)
    scheduler = get_docling_conversion_scheduler(registry)
    parser_registry = get_parser_registry(settings, scheduler)
    parse_service = get_document_parse_service(settings, parser_registry)
    job_repository = get_job_repository(settings)
    dispatch_service = get_embedding_dispatch_service(
        settings,
        get_embedding_queue_service(settings),
        job_repository,
        get_job_queue_publisher(settings),
    )
    return get_parser_worker_service(
        settings,
        parse_service,
        job_repository,
        dispatch_service,
    )


def build_dispatch_service() -> Any:
    from ingest_orquestator_server.api.dependencies import (
        get_embedding_dispatch_service,
        get_embedding_queue_service,
        get_job_repository,
    )
    from ingest_orquestator_server.config.settings import get_settings

    settings = get_settings()
    job_repository = get_job_repository(settings)
    return get_embedding_dispatch_service(
        settings,
        get_embedding_queue_service(settings),
        job_repository,
        None,
    )
