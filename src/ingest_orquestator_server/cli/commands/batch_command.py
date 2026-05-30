from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from ingest_orquestator_server.application.exceptions import (
    UnsupportedDocumentFormatError,
    UnsupportedIngestionOptionError,
    UnsupportedParserError,
    UnsupportedPipelineError,
)
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


def batch(
    inputs: Annotated[list[Path], typer.Argument(exists=True, readable=True)],
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", "-o", help="Directory where parse artifacts are written."),
    ] = None,
    parser: Annotated[
        str,
        typer.Option("--parser", "-p", help="Parser backend to use."),
    ] = "docling",
    pipeline: Annotated[
        str | None,
        typer.Option("--pipeline", help="Docling pipeline: standard, vlm, or auto."),
    ] = None,
    profile: Annotated[
        str | None,
        typer.Option("--profile", help="Ingestion profile to apply to the batch."),
    ] = None,
    chunking_enabled: Annotated[
        bool | None,
        typer.Option("--chunking/--no-chunking", help="Override chunking for this batch."),
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
    file_paths = _collect_file_paths(inputs, allowed_extensions=settings.allowed_upload_extensions)
    parse_service = DocumentParseService(
        parser_registry=build_parser_registry(settings),
        output_writer=LocalParseOutputWriter(),
        chunking_service=DocumentChunkingService(settings),
        embedding_output_enabled=settings.embedding_output_enabled,
    )
    try:
        results = parse_service.parse_files(
            file_paths=file_paths,
            parser_name=parser,
            output_root=output_dir or settings.outputs_dir,
            pipeline=pipeline,
            profile=profile,
            chunking_enabled=chunking_enabled,
            chunking_strategy=chunking_strategy,
        )
    except UnsupportedParserError as exc:
        raise typer.BadParameter(str(exc), param_hint="--parser") from exc
    except UnsupportedPipelineError as exc:
        raise typer.BadParameter(str(exc), param_hint="--pipeline") from exc
    except UnsupportedIngestionOptionError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except UnsupportedDocumentFormatError as exc:
        raise typer.BadParameter(str(exc), param_hint="inputs") from exc

    typer.echo(
        json.dumps(
            {
                "file_count": len(file_paths),
                "completed_count": len(results),
                "results": [
                    {
                        "document_id": result.parse_output.document.document_id,
                        "source_file_name": result.parse_output.document.source_file_name,
                        "page_count": result.parse_output.document.page_count,
                        "element_count": len(result.parse_output.document.elements),
                        "chunk_count": len(result.chunks),
                        "embedding_record_count": len(result.embedding_records),
                        "metadata": result.diagnostics.metadata,
                        "outputs": result.outputs.model_dump(mode="json"),
                    }
                    for result in results
                ],
            },
            indent=2,
        )
    )


def _collect_file_paths(
    inputs: list[Path],
    *,
    allowed_extensions: list[str],
) -> list[Path]:
    allowed = {extension.lower() for extension in allowed_extensions}
    file_paths: list[Path] = []
    for input_path in inputs:
        path = input_path.expanduser().resolve()
        if path.is_dir():
            file_paths.extend(
                sorted(
                    child
                    for child in path.rglob("*")
                    if child.is_file() and child.suffix.lower() in allowed
                )
            )
        elif path.is_file():
            file_paths.append(path)

    if not file_paths:
        raise typer.BadParameter("No supported input files were found.", param_hint="inputs")
    return file_paths
