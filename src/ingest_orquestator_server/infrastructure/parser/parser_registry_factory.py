from __future__ import annotations

from ingest_orquestator_server.application.parser_registry import ParserRegistry
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.docling.docling_document_parser import (
    DoclingDocumentParser,
)
from ingest_orquestator_server.infrastructure.docling.docling_engine import (
    DoclingConversionScheduler,
)


def build_parser_registry(
    settings: Settings,
    *,
    docling_conversion_scheduler: DoclingConversionScheduler | None = None,
) -> ParserRegistry:
    return ParserRegistry(
        {
            "docling": lambda: DoclingDocumentParser(
                settings=settings,
                conversion_scheduler=docling_conversion_scheduler,
            ),
        }
    )
