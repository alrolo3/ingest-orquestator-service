import typer

from ingest_orquestator_server.cli.commands.cleanup_command import cleanup
from ingest_orquestator_server.cli.commands.parse_command import parse

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """Run ingestion orchestration commands."""


app.command()(parse)
app.command()(cleanup)
