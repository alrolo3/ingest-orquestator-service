from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ingest_orquestator_server.application.parser_registry import ParserRegistry
from ingest_orquestator_server.application.ports.parse_output_writer import ParseOutputWriter
from ingest_orquestator_server.models.output_files import OutputFiles
from ingest_orquestator_server.models.parse_output import ParseOutput


@dataclass(frozen=True)
class DocumentParseResult:
    parse_output: ParseOutput
    outputs: OutputFiles


class DocumentParseService:
    def __init__(
        self,
        *,
        parser_registry: ParserRegistry,
        output_writer: ParseOutputWriter,
    ) -> None:
        self._parser_registry = parser_registry
        self._output_writer = output_writer

    def parse_file(
        self,
        *,
        file_path: Path,
        parser_name: str,
        output_root: Path,
        document_id: str | None = None,
    ) -> DocumentParseResult:
        parser = self._parser_registry.get(parser_name)
        parse_output = parser.parse(file_path, document_id=document_id)
        outputs = self._output_writer.write(parse_output, output_root)
        return DocumentParseResult(parse_output=parse_output, outputs=outputs)
