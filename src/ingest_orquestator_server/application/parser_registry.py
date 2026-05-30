from __future__ import annotations

from collections.abc import Callable

from ingest_orquestator_server.application.exceptions import UnsupportedParserError
from ingest_orquestator_server.application.ports.document_parser import DocumentParser

ParserFactory = Callable[[], DocumentParser]


class ParserRegistry:
    def __init__(self, parser_factories: dict[str, ParserFactory]) -> None:
        self._parser_factories = parser_factories

    def get(self, parser_name: str) -> DocumentParser:
        parser_factory = self._parser_factories.get(parser_name)
        if parser_factory is None:
            raise UnsupportedParserError(parser_name)
        return parser_factory()
