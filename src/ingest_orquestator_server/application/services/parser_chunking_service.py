from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ingest_orquestator_server.application.exceptions import UnsupportedIngestionOptionError
from ingest_orquestator_server.application.ports.parser_chunker import ParserChunker
from ingest_orquestator_server.models.chunking import (
    ChunkingSelection,
    ChunkingStrategy,
    ParserChunkingCapabilities,
    normalize_chunking_strategy,
)
from ingest_orquestator_server.models.document_chunk import DocumentChunk
from ingest_orquestator_server.models.parsed_document import ParsedDocument


class ParserChunkingService:
    def __init__(
        self,
        chunkers: Mapping[str, ParserChunker],
        *,
        default_enabled: bool,
        default_strategy: str | ChunkingStrategy | None,
    ) -> None:
        self._chunkers = chunkers
        self._default_enabled = default_enabled
        self._default_strategy = self._normalize(default_strategy)

    def capabilities_for(self, parser_name: str) -> ParserChunkingCapabilities:
        chunker = self._chunkers.get(parser_name)
        if chunker is None:
            return ParserChunkingCapabilities(
                enabled=False,
                default_strategy=None,
                strategies=[],
            )
        return chunker.capabilities()

    def resolve_selection(
        self,
        *,
        parser_name: str,
        chunking_enabled: bool | None,
        chunking_strategy: str | ChunkingStrategy | None,
    ) -> ChunkingSelection:
        enabled = self._default_enabled if chunking_enabled is None else chunking_enabled
        requested_strategy = self._normalize(chunking_strategy) or self._default_strategy
        if not enabled:
            return ChunkingSelection(enabled=False, strategy=requested_strategy)
        if requested_strategy is None:
            raise UnsupportedIngestionOptionError(
                "chunking_strategy is required when chunking_enabled=true"
            )
        return ChunkingSelection(enabled=True, strategy=requested_strategy)

    def validate_request(
        self,
        *,
        parser_name: str,
        chunking_enabled: bool | None,
        chunking_strategy: str | ChunkingStrategy | None,
    ) -> None:
        selection = self.resolve_selection(
            parser_name=parser_name,
            chunking_enabled=chunking_enabled,
            chunking_strategy=chunking_strategy,
        )
        if selection.strategy is None:
            return
        if selection.enabled:
            self.validate_strategy(parser_name=parser_name, strategy=selection.strategy)
            return
        if chunking_strategy is not None:
            self._validate_supported_strategy(
                parser_name=parser_name,
                strategy=selection.strategy,
            )

    def validate_strategy(self, *, parser_name: str, strategy: ChunkingStrategy) -> None:
        chunker = self._validate_supported_strategy(
            parser_name=parser_name,
            strategy=strategy,
        )
        chunker.validate_strategy(strategy)

    def _validate_supported_strategy(
        self,
        *,
        parser_name: str,
        strategy: ChunkingStrategy,
    ) -> ParserChunker:
        chunker = self._chunkers.get(parser_name)
        if chunker is None:
            raise UnsupportedIngestionOptionError(
                f"Parser '{parser_name}' does not support chunking"
            )
        capabilities = chunker.capabilities()
        if not capabilities.supports(strategy):
            raise UnsupportedIngestionOptionError(
                f"Parser '{parser_name}' does not support chunking strategy "
                f"'{strategy.value}'"
            )
        return chunker

    def chunk(
        self,
        document: ParsedDocument,
        *,
        parser_name: str,
        chunking_document: Any | None,
        chunking_enabled: bool | None,
        chunking_strategy: str | ChunkingStrategy | None,
    ) -> tuple[list[DocumentChunk], ChunkingSelection]:
        selection = self.resolve_selection(
            parser_name=parser_name,
            chunking_enabled=chunking_enabled,
            chunking_strategy=chunking_strategy,
        )
        if not selection.enabled:
            return [], selection
        if selection.strategy is None:
            raise UnsupportedIngestionOptionError(
                "chunking_strategy is required when chunking_enabled=true"
            )
        self.validate_strategy(parser_name=parser_name, strategy=selection.strategy)
        chunker = self._chunkers[parser_name]
        return (
            chunker.chunk(
                document,
                chunking_document=chunking_document,
                strategy=selection.strategy,
            ),
            selection,
        )

    @staticmethod
    def _normalize(
        strategy: str | ChunkingStrategy | None,
    ) -> ChunkingStrategy | None:
        if strategy is None:
            return None
        try:
            return normalize_chunking_strategy(strategy)
        except ValueError as exc:
            raise UnsupportedIngestionOptionError(str(exc)) from exc
