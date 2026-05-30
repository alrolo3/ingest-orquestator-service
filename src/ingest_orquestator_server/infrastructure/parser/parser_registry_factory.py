from __future__ import annotations

from ingest_orquestator_server.application.parser_registry import ParserRegistry
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.docling.docling_document_parser import (
    DoclingDocumentParser,
)


def build_parser_registry(settings: Settings) -> ParserRegistry:
    return ParserRegistry(
        {
            "docling": lambda: DoclingDocumentParser(settings=settings),
        }
    )
