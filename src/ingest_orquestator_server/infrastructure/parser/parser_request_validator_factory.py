from __future__ import annotations

from ingest_orquestator_server.application.validation.parser_request_validator import (
    ParserRequestValidationService,
    ParserRequestValidator,
)
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.docling.docling_chunker import (
    DoclingParserChunker,
)
from ingest_orquestator_server.infrastructure.docling.docling_parser_request_validator import (
    DoclingParserRequestValidator,
)


def build_parser_request_validator(settings: Settings) -> ParserRequestValidator:
    return ParserRequestValidationService(
        {"docling": DoclingParserRequestValidator(settings)},
        {"docling": DoclingParserChunker(settings)},
        default_chunking_enabled=settings.chunking_enabled,
        default_chunking_strategy=settings.chunking_strategy,
    )
