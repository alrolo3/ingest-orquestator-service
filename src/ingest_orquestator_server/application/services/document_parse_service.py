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
from ingest_orquestator_server.application.services.rag_ingestion_record_service import (
    RagIngestionRecordService,
)
from ingest_orquestator_server.models.output_files import OutputFiles
from ingest_orquestator_server.models.parse_diagnostics import ParseDiagnostics
from ingest_orquestator_server.models.parse_output import ParseOutput
from ingest_orquestator_server.models.parse_progress import ParseProgressCallback
from ingest_orquestator_server.models.parsed_document_content import ParsedDocumentContent


@dataclass(frozen=True)
class DocumentParseResult:
    content: ParsedDocumentContent
    outputs: OutputFiles | None
    diagnostics: ParseDiagnostics


class DocumentParseService:
    def __init__(
        self,
        *,
        parser_registry: ParserRegistry,
        output_writer: ParseOutputWriter,
        chunking_service: DocumentChunkingService,
        rag_record_service: RagIngestionRecordService | None = None,
        embedding_output_enabled: bool = True,
    ) -> None:
        self._parser_registry = parser_registry
        self._output_writer = output_writer
        self._chunking_service = chunking_service
        self._rag_record_service = rag_record_service or RagIngestionRecordService()

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
        ocr_languages: list[str] | None = None,
        include_html: bool = False,
        progress_callback: ParseProgressCallback | None = None,
    ) -> DocumentParseResult:
        parser = self._parser_registry.get(parser_name)
        started_at = datetime.now(UTC)
        started = perf_counter()
        parse_kwargs = {
            "document_id": document_id,
            "pipeline": pipeline,
            "include_html": include_html,
            "progress_callback": progress_callback,
        }
        if ocr_languages is not None:
            parse_kwargs["ocr_languages"] = ocr_languages
        parse_output = parser.parse(file_path, **parse_kwargs)
        return self._build_parse_result(
            parse_output,
            parser_name=parser_name,
            output_root=output_root,
            pipeline=pipeline,
            chunking_enabled=chunking_enabled,
            chunking_strategy=chunking_strategy,
            include_html=include_html,
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
        ocr_languages: list[str] | None = None,
        include_html: bool = False,
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
                    ocr_languages=ocr_languages,
                    include_html=include_html,
                )
                for file_path in file_paths
            ]

        started_at = datetime.now(UTC)
        started = perf_counter()
        parse_many_kwargs = {"pipeline": pipeline, "include_html": include_html}
        if ocr_languages is not None:
            parse_many_kwargs["ocr_languages"] = ocr_languages
        parse_outputs = parse_many(file_paths, **parse_many_kwargs)
        return [
            self._build_parse_result(
                parse_output,
                parser_name=parser_name,
                output_root=output_root,
                pipeline=pipeline,
                chunking_enabled=chunking_enabled,
                chunking_strategy=chunking_strategy,
                include_html=include_html,
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
        include_html: bool,
        started_at: datetime,
        started: float,
    ) -> DocumentParseResult:
        if parse_output.normalized_document is None:
            raise RuntimeError("Parser output did not include a normalized document.")
        chunking_is_enabled = self._chunking_service.is_enabled(
            chunking_enabled=chunking_enabled,
        )
        requested_chunking_strategy = self._chunking_service.strategy(
            chunking_strategy=chunking_strategy,
        )
        chunks = self._chunking_service.chunk(
            parse_output.normalized_document,
            chunking_document=parse_output.chunking_document,
            chunking_enabled=chunking_enabled,
            chunking_strategy=chunking_strategy,
        )
        pipeline_name = parse_output.metadata.get("pipeline")
        input_format = parse_output.metadata.get("input_format")
        rag_records = self._rag_record_service.build_records(
            document=parse_output.normalized_document,
            chunks=chunks,
            job_id=parse_output.document_id,
            parser=parser_name,
            pipeline=str(pipeline_name) if pipeline_name is not None else pipeline,
            input_format=str(input_format) if input_format is not None else None,
            confidence_summary=parse_output.confidence_summary,
            warnings=parse_output.warnings,
        )
        completed_at = datetime.now(UTC)
        diagnostics = ParseDiagnostics(
            parser=parser_name,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=round((perf_counter() - started) * 1000),
            chunk_count=len(chunks),
            metadata={
                **parse_output.metadata,
                "chunking_enabled": chunking_is_enabled,
                "chunking_strategy": chunks[0].metadata.get("chunker_strategy")
                if chunks
                else requested_chunking_strategy,
                "rag_record_count": len(rag_records),
                "include_html": include_html,
                "conversion_status": parse_output.conversion_status,
                "conversion_errors": parse_output.conversion_errors,
                "conversion_timings": parse_output.conversion_timings,
                "confidence_summary": parse_output.confidence_summary,
                "warning_count": len(parse_output.warnings),
                "warnings": parse_output.warnings,
            },
        )
        content = ParsedDocumentContent(
            document_id=parse_output.document_id,
            markdown=parse_output.markdown,
            html=parse_output.html,
            metadata={
                **diagnostics.metadata,
                "document_id": parse_output.document_id,
                "job_id": parse_output.document_id,
                "parser": parser_name,
                "title": parse_output.title,
                "source_file_name": parse_output.source_file_name,
                "page_count": parse_output.normalized_document.page_count,
                "timings": {
                    "started_at": started_at.isoformat(),
                    "completed_at": completed_at.isoformat(),
                    "duration_ms": diagnostics.duration_ms,
                },
            },
            rag_records=rag_records,
        )
        outputs = None
        if output_root is not None:
            outputs = self.write_parse_result(
                content=content,
                output_root=output_root,
                diagnostics=diagnostics,
            )
        return DocumentParseResult(
            content=content,
            outputs=outputs,
            diagnostics=diagnostics,
        )

    def write_parse_result(
        self,
        *,
        content: ParsedDocumentContent,
        output_root: Path,
        diagnostics: ParseDiagnostics,
    ) -> OutputFiles:
        return self._output_writer.write(
            content,
            output_root,
            diagnostics=diagnostics,
        )
