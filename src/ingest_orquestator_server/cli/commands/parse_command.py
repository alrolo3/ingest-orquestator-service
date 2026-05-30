from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from ingest_orquestator_server.application.exceptions import (
    UnsupportedDocumentFormatError,
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


def parse(
    file: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", "-o", help="Directory where parse artifacts are written."),
    ] = None,
    parser: Annotated[
        str,
        typer.Option("--parser", "-p", help="Parser backend to use."),
    ] = "docling",
    pipeline: Annotated[
        str,
        typer.Option("--pipeline", help="Docling pipeline: standard, vlm, or auto."),
    ] = "standard",
) -> None:
    settings = get_settings()
    parse_service = DocumentParseService(
        parser_registry=build_parser_registry(settings),
        output_writer=LocalParseOutputWriter(),
        chunking_service=DocumentChunkingService(settings),
        embedding_output_enabled=settings.embedding_output_enabled,
    )
    try:
        result = parse_service.parse_file(
            file_path=file,
            parser_name=parser,
            output_root=output_dir or settings.outputs_dir,
            pipeline=pipeline,
        )
    except UnsupportedParserError as exc:
        raise typer.BadParameter(str(exc), param_hint="--parser") from exc
    except UnsupportedPipelineError as exc:
        raise typer.BadParameter(str(exc), param_hint="--pipeline") from exc
    except UnsupportedDocumentFormatError as exc:
        raise typer.BadParameter(str(exc), param_hint="file") from exc

    typer.echo(
        json.dumps(
            {
                "document_id": result.parse_output.document.document_id,
                "source_file_name": result.parse_output.document.source_file_name,
                "page_count": result.parse_output.document.page_count,
                "element_count": len(result.parse_output.document.elements),
                "chunk_count": len(result.chunks),
                "embedding_record_count": len(result.embedding_records),
                "metadata": result.diagnostics.metadata,
                "outputs": result.outputs.model_dump(mode="json"),
            },
            indent=2,
        )
    )
