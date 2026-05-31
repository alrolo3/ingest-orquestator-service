from __future__ import annotations

from typing import Protocol

from ingest_orquestator_server.models.embedding_queue import (
    EmbeddingDispatchResult,
    EmbeddingQueueItem,
    EmbeddingTaskStatus,
)


class EmbeddingDispatcher(Protocol):
    def submit_batch(self, items: list[EmbeddingQueueItem]) -> EmbeddingDispatchResult:
        """Submit a batch of parsed documents to the remote embedding system."""

    def get_task_status(self, task_id: str) -> EmbeddingTaskStatus:
        """Return the remote async task status."""
