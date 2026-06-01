from __future__ import annotations

from typing import Protocol

from ingest_orquestator_server.models.parsed_document_dispatch import (
    DispatchSinkResult,
    ParsedDocumentDispatchItem,
)


class ParsedDocumentDispatchSink(Protocol):
    def submit_batch(
        self, items: list[ParsedDocumentDispatchItem]
    ) -> DispatchSinkResult:
        """Submit parsed document RAG records to an output sink."""
