from pathlib import Path

from ingest_orquestator_server.application.parser_registry import ParserRegistry
from ingest_orquestator_server.cli.commands import parse_command
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.docling.docling_document_parser import (
    DoclingDocumentParser,
)
from tests.fakes.fake_docling_converter import FakeDoclingConverter


def test_cli_parse_accepts_auto_pipeline(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    input_path = tmp_path / "example.md"
    input_path.write_text("# Example\n", encoding="utf-8")
    settings = Settings(
        storage_dir=tmp_path,
        allowed_upload_extensions=[".md"],
        docling_allowed_formats=["md"],
    )

    monkeypatch.setattr(parse_command, "get_settings", lambda: settings)
    monkeypatch.setattr(
        parse_command,
        "build_parser_registry",
        lambda _settings: ParserRegistry(
            {
                "docling": lambda: DoclingDocumentParser(
                    converter=FakeDoclingConverter(),
                    settings=settings,
                )
            }
        ),
    )

    parse_command.parse(
        file=input_path,
        output_dir=tmp_path / "outputs",
        parser="docling",
        pipeline="auto",
    )

    captured = capsys.readouterr()
    assert '"pipeline": "standard"' in captured.out
    assert '"embedding_record_count": 1' in captured.out
