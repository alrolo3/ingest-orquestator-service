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
                    pipeline=pipeline,
                )
                results.append(
                    {
                        "file": str(file),
                        "pipeline": pipeline,
                        "status": "completed",
                        "duration_ms": result.diagnostics.duration_ms,
                        "page_count": result.parse_output.document.page_count,
                        "element_count": len(result.parse_output.document.elements),
                        "chunk_count": len(result.chunks),
                        "embedding_record_count": len(result.embedding_records),
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
        "| File | Pipeline | Status | Duration ms | Pages | Elements | Chunks |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for result in results:
        lines.append(
            "| {file} | {pipeline} | {status} | {duration_ms} | {page_count} | "
            "{element_count} | {chunk_count} |".format(
                file=result.get("file", ""),
                pipeline=result.get("pipeline", ""),
                status=result.get("status", ""),
                duration_ms=result.get("duration_ms", ""),
                page_count=result.get("page_count", ""),
                element_count=result.get("element_count", ""),
                chunk_count=result.get("chunk_count", ""),
            )
        )
    return "\n".join(lines) + "\n"
