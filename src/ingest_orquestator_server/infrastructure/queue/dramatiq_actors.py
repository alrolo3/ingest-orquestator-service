from __future__ import annotations

import dramatiq

from ingest_orquestator_server.config.settings import get_settings
from ingest_orquestator_server.infrastructure.queue.dramatiq_runtime import (
    build_dispatch_service,
    build_dramatiq_publisher,
    build_parser_worker_service,
    configure_dramatiq_broker,
    dispatch_actor_options,
    parser_actor_options,
)
from ingest_orquestator_server.models.parsed_document_dispatch import (
    ParsedDocumentDispatchItem,
)

_settings = get_settings()
configure_dramatiq_broker(_settings)


@dramatiq.actor(**parser_actor_options(_settings))
def process_parser_job(job_id: str) -> None:
    _process_parser_job(job_id)


@dramatiq.actor(**dispatch_actor_options(_settings))
def process_dispatch_job(item_payload: dict) -> None:
    build_dispatch_service().dispatch_item(
        ParsedDocumentDispatchItem.model_validate(item_payload)
    )


def _process_parser_job(job_id: str) -> None:
    result = build_parser_worker_service().process_job(job_id)
    if result.retry_requested:
        build_dramatiq_publisher(_settings).enqueue_parser_job(job_id)
