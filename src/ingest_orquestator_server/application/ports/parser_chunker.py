from __future__ import annotations

from typing import Any, Protocol

from ingest_orquestator_server.models.chunking import (
    ChunkingStrategy,
    ParserChunkingCapabilities,
)
from ingest_orquestator_server.models.document_chunk import DocumentChunk
from ingest_orquestator_server.models.parsed_document import ParsedDocument


class ParserChunker(Protocol):
    parser_name: str

    def capabilities(self) -> ParserChunkingCapabilities:
        """Return chunking strategies supported by this parser."""

    def validate_strategy(self, strategy: ChunkingStrategy) -> None:
        """Validate that a strategy is supported and ready for this parser."""

    def chunk(
        self,
        document: ParsedDocument,
        *,
        chunking_document: Any | None,
        strategy: ChunkingStrategy,
    ) -> list[DocumentChunk]:
        """Chunk the parsed document using a parser-owned strategy implementation."""
