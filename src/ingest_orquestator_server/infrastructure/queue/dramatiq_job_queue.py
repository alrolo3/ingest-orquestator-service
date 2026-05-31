from __future__ import annotations

from typing import Any, Protocol

from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.models.embedding_queue import EmbeddingQueueItem


class ActorSender(Protocol):
    def send(self, *args: Any, **kwargs: Any) -> Any:
        """Send a dramatiq actor message."""


class DramatiqJobQueuePublisher:
    def __init__(
        self,
        *,
        parser_actor: ActorSender,
        dispatch_actor: ActorSender,
    ) -> None:
        self._parser_actor = parser_actor
        self._dispatch_actor = dispatch_actor

    @classmethod
    def from_settings(cls, settings: Settings) -> DramatiqJobQueuePublisher:
        from ingest_orquestator_server.infrastructure.queue.dramatiq_runtime import (
            build_dramatiq_publisher,
        )

        return build_dramatiq_publisher(settings)

    def enqueue_parser_job(self, job_id: str) -> None:
        self._parser_actor.send(job_id)

    def enqueue_dispatch_job(self, item: EmbeddingQueueItem) -> None:
        self._dispatch_actor.send(item.model_dump(mode="json"))
