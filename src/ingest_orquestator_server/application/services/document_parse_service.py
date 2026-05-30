from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from ingest_orquestator_server.application.parser_registry import ParserRegistry
from ingest_orquestator_server.application.ports.parse_output_writer import ParseOutputWriter
from ingest_orquestator_server.application.services.document_chunking_service import (
    DocumentChunkingService,
)
from ingest_orquestator_server.models.document_chunk import DocumentChunk
from ingest_orquestator_server.models.output_files import OutputFiles
from ingest_orquestator_server.models.parse_diagnostics import ParseDiagnostics
from ingest_orquestator_server.models.parse_output import ParseOutput


@dataclass(frozen=True)
class DocumentParseResult:
    parse_output: ParseOutput
    outputs: OutputFiles
    chunks: list[DocumentChunk]
    diagnostics: ParseDiagnostics


class DocumentParseService:
    def __init__(
        self,
        *,
        parser_registry: ParserRegistry,
        output_writer: ParseOutputWriter,
        chunking_service: DocumentChunkingService,
    ) -> None:
        self._parser_registry = parser_registry
        self._output_writer = output_writer
        self._chunking_service = chunking_service

    def parse_file(
        self,
        *,
        file_path: Path,
        parser_name: str,
        output_root: Path,
        document_id: str | None = None,
    ) -> DocumentParseResult:
        parser = self._parser_registry.get(parser_name)
        started_at = datetime.now(UTC)
        started = perf_counter()
        parse_output = parser.parse(file_path, document_id=document_id)
        chunks = self._chunking_service.chunk(parse_output.document)
        completed_at = datetime.now(UTC)
        diagnostics = ParseDiagnostics(
            parser=parser_name,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=round((perf_counter() - started) * 1000),
            chunk_count=len(chunks),
            metadata={
                "source_file_name": parse_output.document.source_file_name,
                "page_count": parse_output.document.page_count,
                "element_count": len(parse_output.document.elements),
            },
        )
        outputs = self._output_writer.write(
            parse_output,
            output_root,
            chunks=chunks,
            diagnostics=diagnostics,
        )
        return DocumentParseResult(
            parse_output=parse_output,
            outputs=outputs,
            chunks=chunks,
            diagnostics=diagnostics,
        )
