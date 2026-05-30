from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from ingest_orquestator_server.application.parser_registry import ParserRegistry
from ingest_orquestator_server.application.services.document_parse_service import (
    DocumentParseService,
)
from ingest_orquestator_server.config.settings import get_settings
from ingest_orquestator_server.infrastructure.docling.docling_document_parser import (
    DoclingDocumentParser,
)
from ingest_orquestator_server.infrastructure.filesystem.local_parse_output_writer import (
    LocalParseOutputWriter,
)


def parse(
    file: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", "-o", help="Directory where parse artifacts are written."),
    ] = None,
) -> None:
    settings = get_settings()
    parse_service = DocumentParseService(
        parser_registry=ParserRegistry(
            {
                "docling": lambda: DoclingDocumentParser(settings=settings),
            }
        ),
        output_writer=LocalParseOutputWriter(),
    )
    result = parse_service.parse_file(
        file_path=file,
        parser_name="docling",
        output_root=output_dir or settings.outputs_dir,
    )

    typer.echo(
        json.dumps(
            {
                "document_id": result.parse_output.document.document_id,
                "source_file_name": result.parse_output.document.source_file_name,
                "page_count": result.parse_output.document.page_count,
                "element_count": len(result.parse_output.document.elements),
                "outputs": result.outputs.model_dump(mode="json"),
            },
            indent=2,
        )
    )
