from __future__ import annotations

import dramatiq

from ingest_orquestator_server.config.settings import get_settings
from ingest_orquestator_server.infrastructure.queue.dramatiq_runtime import (
    build_dispatch_service,
    build_parser_worker_service,
    configure_dramatiq_broker,
)
from ingest_orquestator_server.models.parsed_document_dispatch import (
    ParsedDocumentDispatchItem,
)

_settings = get_settings()
configure_dramatiq_broker(_settings)


@dramatiq.actor(queue_name=_settings.dramatiq_parser_queue_name)
def process_parser_job(job_id: str) -> None:
    build_parser_worker_service().process_job(job_id)


@dramatiq.actor(queue_name=_settings.dramatiq_dispatch_queue_name)
def process_dispatch_job(item_payload: dict) -> None:
    build_dispatch_service().dispatch_item(
        ParsedDocumentDispatchItem.model_validate(item_payload)
    )
