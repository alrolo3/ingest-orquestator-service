from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from ingest_orquestator_server.config import get_settings
from ingest_orquestator_server.output_writer import write_parse_output
from ingest_orquestator_server.parsers.docling_parser import DoclingParser

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """Run ingestion orchestration commands."""


@app.command()
def parse(
    file: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", "-o", help="Directory where parse artifacts are written."),
    ] = None,
) -> None:
    settings = get_settings()
    target_output_dir = output_dir or settings.outputs_dir
    parse_output = DoclingParser().parse(file)
    outputs = write_parse_output(parse_output, target_output_dir)

    typer.echo(
        json.dumps(
            {
                "document_id": parse_output.document.document_id,
                "source_file_name": parse_output.document.source_file_name,
                "page_count": parse_output.document.page_count,
                "element_count": len(parse_output.document.elements),
                "outputs": outputs.model_dump(mode="json"),
            },
            indent=2,
        )
    )
