from __future__ import annotations

from typing import Any, Protocol

from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.models.parsed_document_dispatch import (
    ParsedDocumentDispatchItem,
)


class ActorSender(Protocol):
    def send(self, *args: Any, **kwargs: Any) -> Any:
        """Send a dramatiq actor message."""

    def send_with_options(
        self,
        *,
        args: tuple[Any, ...],
        kwargs: dict[str, Any] | None = None,
        **options: Any,
    ) -> Any:
        """Send a dramatiq actor message with explicit message options."""


class DramatiqJobQueuePublisher:
    def __init__(
        self,
        *,
        parser_actor: ActorSender,
        dispatch_actor: ActorSender,
        parser_time_limit_ms: int,
        dispatch_time_limit_ms: int,
    ) -> None:
        self._parser_actor = parser_actor
        self._dispatch_actor = dispatch_actor
        self._parser_time_limit_ms = parser_time_limit_ms
        self._dispatch_time_limit_ms = dispatch_time_limit_ms

    @classmethod
    def from_settings(cls, settings: Settings) -> DramatiqJobQueuePublisher:
        from ingest_orquestator_server.infrastructure.queue.dramatiq_runtime import (
            build_dramatiq_publisher,
        )

        return build_dramatiq_publisher(settings)

    def enqueue_parser_job(self, job_id: str) -> None:
        self._parser_actor.send_with_options(
            args=(job_id,),
            time_limit=self._parser_time_limit_ms,
        )

    def enqueue_dispatch_job(self, item: ParsedDocumentDispatchItem) -> None:
        self._dispatch_actor.send_with_options(
            args=(item.model_dump(mode="json"),),
            time_limit=self._dispatch_time_limit_ms,
        )
