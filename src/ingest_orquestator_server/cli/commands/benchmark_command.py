from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from ingest_orquestator_server.application.services.document_chunking_service import (
    DocumentChunkingService,
)
from ingest_orquestator_server.application.services.document_parse_service import (
    DocumentParseService,
)
from ingest_orquestator_server.config.settings import get_settings
from ingest_orquestator_server.infrastructure.filesystem.local_parse_output_writer import (
    LocalParseOutputWriter,
)
from ingest_orquestator_server.infrastructure.parser.parser_registry_factory import (
    build_parser_registry,
)


def benchmark(
    files: Annotated[list[Path], typer.Argument(exists=True, dir_okay=False, readable=True)],
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", "-o", help="Directory where benchmark artifacts are written."),
    ] = None,
    parser: Annotated[
        str,
        typer.Option("--parser", "-p", help="Parser backend to use."),
    ] = "docling",
    pipelines: Annotated[
        str,
        typer.Option(
            "--pipelines",
            help="Comma-separated pipelines to run, for example standard,vlm.",
        ),
    ] = "standard",
    profile: Annotated[
        str | None,
        typer.Option("--profile", help="Ingestion profile to apply to each benchmark run."),
    ] = None,
    chunking_enabled: Annotated[
        bool | None,
        typer.Option("--chunking/--no-chunking", help="Override chunking for each run."),
    ] = None,
    chunking_strategy: Annotated[
        str | None,
        typer.Option(
            "--chunking-strategy",
            help="Chunking strategy: hybrid, line_based, or legacy_char.",
        ),
    ] = None,
) -> None:
    settings = get_settings()
    benchmark_root = output_dir or (settings.storage_dir / "benchmarks")
    benchmark_root.mkdir(parents=True, exist_ok=True)
    run_dir = benchmark_root / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True, exist_ok=True)
    parse_service = DocumentParseService(
        parser_registry=build_parser_registry(settings),
        output_writer=LocalParseOutputWriter(),
        chunking_service=DocumentChunkingService(settings),
        embedding_output_enabled=settings.embedding_output_enabled,
    )

    pipeline_values = [item.strip() for item in pipelines.split(",") if item.strip()]
    results = []
    for file in files:
        for pipeline in pipeline_values:
            try:
                result = parse_service.parse_file(
                    file_path=file,
                    parser_name=parser,
                    output_root=run_dir,
                    pipeline=pipeline or None,
                    profile=profile,
                    chunking_enabled=chunking_enabled,
                    chunking_strategy=chunking_strategy,
                )
                confidence_summary = result.parse_output.confidence_summary
                results.append(
                    {
                        "file": str(file),
                        "pipeline": pipeline,
                        "profile": result.diagnostics.metadata.get("profile"),
                        "status": "completed",
                        "duration_ms": result.diagnostics.duration_ms,
                        "page_count": result.parse_output.document.page_count,
                        "element_count": len(result.parse_output.document.elements),
                        "chunk_count": len(result.chunks),
                        "embedding_record_count": len(result.embedding_records),
                        "chunking_strategy": result.diagnostics.metadata.get("chunking_strategy"),
                        "conversion_status": result.parse_output.conversion_status,
                        "confidence_summary": confidence_summary,
                        "warning_count": len(result.parse_output.warnings),
                        "outputs": result.outputs.model_dump(mode="json"),
                        "metadata": result.diagnostics.metadata,
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "file": str(file),
                        "pipeline": pipeline,
                        "status": "failed",
                        "error": str(exc),
                        "error_type": type(exc).__name__,
                    }
                )

    summary = {"results": results}
    summary_path = run_dir / "benchmark.json"
    markdown_path = run_dir / "benchmark.md"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    markdown_path.write_text(_render_markdown(results), encoding="utf-8")
    typer.echo(json.dumps({"output_dir": str(run_dir), **summary}, indent=2))


def _render_markdown(results: list[dict[str, object]]) -> str:
    lines = [
        "# Docling Pipeline Benchmark",
        "",
        "| File | Pipeline | Profile | Status | Duration ms | Pages | Elements | "
        "Chunks | Confidence | Warnings |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for result in results:
        confidence_summary = result.get("confidence_summary")
        confidence = ""
        if isinstance(confidence_summary, dict):
            confidence = str(confidence_summary.get("mean_score", ""))
        lines.append(
            "| {file} | {pipeline} | {profile} | {status} | {duration_ms} | {page_count} | "
            "{element_count} | {chunk_count} | {confidence} | {warning_count} |".format(
                file=result.get("file", ""),
                pipeline=result.get("pipeline", ""),
                profile=result.get("profile", ""),
                status=result.get("status", ""),
                duration_ms=result.get("duration_ms", ""),
                page_count=result.get("page_count", ""),
                element_count=result.get("element_count", ""),
                chunk_count=result.get("chunk_count", ""),
                confidence=confidence,
                warning_count=result.get("warning_count", ""),
            )
        )
    return "\n".join(lines) + "\n"
