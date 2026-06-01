from __future__ import annotations

from ingest_orquestator_server.application.services.parser_chunking_service import (
    ParserChunkingService,
)
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.docling.docling_chunker import (
    DoclingParserChunker,
)


def build_parser_chunking_service(settings: Settings) -> ParserChunkingService:
    return ParserChunkingService(
        {"docling": DoclingParserChunker(settings)},
        default_enabled=settings.chunking_enabled,
        default_strategy=settings.chunking_strategy,
    )
