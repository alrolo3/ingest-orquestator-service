from __future__ import annotations

from typing import Protocol

from ingest_orquestator_server.models.parsed_document_dispatch import (
    ParsedDocumentDispatchItem,
)


class ParserJobQueue(Protocol):
    def enqueue_parser_job(self, job_id: str) -> None:
        """Publish a parser job for asynchronous processing."""
        ...


class DispatchJobQueue(Protocol):
    def enqueue_dispatch_job(self, item: ParsedDocumentDispatchItem) -> None:
        """Publish a dispatch job for asynchronous output handling."""
        ...


class JobQueuePublisher(ParserJobQueue, DispatchJobQueue, Protocol):
    """Queue publisher for parser and dispatcher handoff messages."""
