from __future__ import annotations

from typing import Protocol

from ingest_orquestator_server.models.embedding_queue import (
    EmbeddingDispatchResult,
    EmbeddingQueueItem,
)


class EmbeddingDispatcher(Protocol):
    def submit_batch(self, items: list[EmbeddingQueueItem]) -> EmbeddingDispatchResult:
        """Submit a batch of parsed documents to the remote embedding system."""
