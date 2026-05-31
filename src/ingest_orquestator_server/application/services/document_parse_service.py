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
from ingest_orquestator_server.application.services.embedding_record_service import (
    EmbeddingRecordService,
)
from ingest_orquestator_server.models.document_chunk import DocumentChunk
from ingest_orquestator_server.models.embedding_record import EmbeddingRecord
from ingest_orquestator_server.models.output_files import OutputFiles
from ingest_orquestator_server.models.parse_diagnostics import ParseDiagnostics
from ingest_orquestator_server.models.parse_output import ParseOutput


@dataclass(frozen=True)
class DocumentParseResult:
    parse_output: ParseOutput
    outputs: OutputFiles | None
    chunks: list[DocumentChunk]
    embedding_records: list[EmbeddingRecord]
    diagnostics: ParseDiagnostics


class DocumentParseService:
    def __init__(
        self,
        *,
        parser_registry: ParserRegistry,
        output_writer: ParseOutputWriter,
        chunking_service: DocumentChunkingService,
        embedding_record_service: EmbeddingRecordService | None = None,
        embedding_output_enabled: bool = True,
    ) -> None:
        self._parser_registry = parser_registry
        self._output_writer = output_writer
        self._chunking_service = chunking_service
        self._embedding_record_service = embedding_record_service or EmbeddingRecordService()
        self._embedding_output_enabled = embedding_output_enabled

    def parse_file(
        self,
        *,
        file_path: Path,
        parser_name: str,
        output_root: Path | None = None,
        document_id: str | None = None,
        pipeline: str | None = None,
        chunking_enabled: bool | None = None,
        chunking_strategy: str | None = None,
    ) -> DocumentParseResult:
        parser = self._parser_registry.get(parser_name)
        started_at = datetime.now(UTC)
        started = perf_counter()
        parse_output = parser.parse(
            file_path,
            document_id=document_id,
            pipeline=pipeline,
        )
        return self._build_parse_result(
            parse_output,
            parser_name=parser_name,
            output_root=output_root,
            pipeline=pipeline,
            chunking_enabled=chunking_enabled,
            chunking_strategy=chunking_strategy,
            started_at=started_at,
            started=started,
        )

    def parse_files(
        self,
        *,
        file_paths: list[Path],
        parser_name: str,
        output_root: Path | None = None,
        pipeline: str | None = None,
        chunking_enabled: bool | None = None,
        chunking_strategy: str | None = None,
    ) -> list[DocumentParseResult]:
        parser = self._parser_registry.get(parser_name)
        parse_many = getattr(parser, "parse_many", None)
        if parse_many is None:
            return [
                self.parse_file(
                    file_path=file_path,
                    parser_name=parser_name,
                    output_root=output_root,
                    pipeline=pipeline,
                    chunking_enabled=chunking_enabled,
                    chunking_strategy=chunking_strategy,
                )
                for file_path in file_paths
            ]

        started_at = datetime.now(UTC)
        started = perf_counter()
        parse_outputs = parse_many(
            file_paths,
            pipeline=pipeline,
        )
        return [
            self._build_parse_result(
                parse_output,
                parser_name=parser_name,
                output_root=output_root,
                pipeline=pipeline,
                chunking_enabled=chunking_enabled,
                chunking_strategy=chunking_strategy,
                started_at=started_at,
                started=started,
            )
            for parse_output in parse_outputs
        ]

    def _build_parse_result(
        self,
        parse_output: ParseOutput,
        *,
        parser_name: str,
        output_root: Path | None,
        pipeline: str | None,
        chunking_enabled: bool | None,
        chunking_strategy: str | None,
        started_at: datetime,
        started: float,
    ) -> DocumentParseResult:
        chunking_is_enabled = self._chunking_service.is_enabled(
            chunking_enabled=chunking_enabled,
        )
        requested_chunking_strategy = self._chunking_service.strategy(
            chunking_strategy=chunking_strategy,
        )
        chunks = self._chunking_service.chunk(
            parse_output.document,
            docling_document=parse_output.docling_document,
            chunking_enabled=chunking_enabled,
            chunking_strategy=chunking_strategy,
        )
        embedding_records = (
            self._embedding_record_service.build_records(
                document=parse_output.document,
                chunks=chunks,
            )
            if self._embedding_output_enabled and chunks
            else []
        )
        completed_at = datetime.now(UTC)
        docling_metadata = parse_output.document.metadata.get("docling", {})
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
                "input_format": docling_metadata.get("input_format"),
                "pipeline": docling_metadata.get("pipeline") or pipeline,
                "ocr_engine": docling_metadata.get("ocr_engine"),
                "vlm_model": docling_metadata.get("vlm_model"),
                "vlm_runtime": docling_metadata.get("vlm_runtime"),
                "vlm_runtime_requested": docling_metadata.get("vlm_runtime_requested"),
                "picture_description_model": docling_metadata.get("picture_description_model"),
                "picture_description_runtime": docling_metadata.get("picture_description_runtime"),
                "picture_description_runtime_requested": docling_metadata.get(
                    "picture_description_runtime_requested"
                ),
                "runtime": docling_metadata.get("runtime"),
                "chunking_enabled": chunking_is_enabled,
                "chunking_strategy": chunks[0].metadata.get("chunker_strategy")
                if chunks
                else requested_chunking_strategy,
                "embedding_record_count": len(embedding_records),
                "conversion_status": parse_output.conversion_status,
                "conversion_errors": parse_output.conversion_errors,
                "conversion_timings": parse_output.conversion_timings,
                "confidence_summary": parse_output.confidence_summary,
                "warning_count": len(parse_output.warnings),
                "warnings": parse_output.warnings,
            },
        )
        outputs = None
        if output_root is not None:
            outputs = self.write_parse_result(
                parse_output=parse_output,
                output_root=output_root,
                chunks=chunks,
                embedding_records=embedding_records,
                diagnostics=diagnostics,
                chunking_enabled=chunking_is_enabled,
            )
        return DocumentParseResult(
            parse_output=parse_output,
            outputs=outputs,
            chunks=chunks,
            embedding_records=embedding_records,
            diagnostics=diagnostics,
        )

    def write_parse_result(
        self,
        *,
        parse_output: ParseOutput,
        output_root: Path,
        chunks: list[DocumentChunk],
        embedding_records: list[EmbeddingRecord],
        diagnostics: ParseDiagnostics,
        chunking_enabled: bool | None = None,
    ) -> OutputFiles:
        return self._output_writer.write(
            parse_output,
            output_root,
            chunks=chunks if chunking_enabled is not False else None,
            embedding_records=embedding_records if embedding_records else None,
            diagnostics=diagnostics,
        )
