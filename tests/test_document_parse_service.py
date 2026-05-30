from pathlib import Path

from ingest_orquestator_server.application.parser_registry import ParserRegistry
from ingest_orquestator_server.application.services.document_chunking_service import (
    DocumentChunkingService,
)
from ingest_orquestator_server.application.services.document_parse_service import (
    DocumentParseService,
)
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.docling.docling_document_parser import (
    DoclingDocumentParser,
)
from ingest_orquestator_server.infrastructure.filesystem.local_parse_output_writer import (
    LocalParseOutputWriter,
)
from tests.fakes.fake_docling_converter import FakeDoclingConverter


def test_parse_file_can_disable_chunking(tmp_path: Path) -> None:
    input_path = tmp_path / "example.md"
    input_path.write_text("# Example\n", encoding="utf-8")
    settings = Settings(storage_dir=tmp_path, docling_allowed_formats=["md"])
    service = _build_service(settings)

    result = service.parse_file(
        file_path=input_path,
        parser_name="docling",
        output_root=tmp_path / "outputs",
        chunking_enabled=False,
    )

    assert result.chunks == []
    assert result.embedding_records == []
    assert result.outputs.chunks_json is None
    assert result.outputs.embedding_input_jsonl is None
    assert result.diagnostics.metadata["chunking_enabled"] is False


def test_parse_files_uses_docling_batch_path(tmp_path: Path) -> None:
    first = tmp_path / "first.md"
    second = tmp_path / "second.md"
    first.write_text("# First\n", encoding="utf-8")
    second.write_text("# Second\n", encoding="utf-8")
    settings = Settings(storage_dir=tmp_path, docling_allowed_formats=["md"])
    service = _build_service(settings)

    results = service.parse_files(
        file_paths=[first, second],
        parser_name="docling",
        output_root=tmp_path / "outputs",
        pipeline="auto",
    )

    assert [result.parse_output.document.source_file_name for result in results] == [
        "first.md",
        "second.md",
    ]
    assert all(result.outputs.manifest_json.exists() for result in results)
    assert all(result.diagnostics.metadata["pipeline"] == "standard" for result in results)


def _build_service(settings: Settings) -> DocumentParseService:
    return DocumentParseService(
        parser_registry=ParserRegistry(
            {
                "docling": lambda: DoclingDocumentParser(
                    converter=FakeDoclingConverter(),
                    settings=settings,
                )
            }
        ),
        output_writer=LocalParseOutputWriter(),
        chunking_service=DocumentChunkingService(settings),
    )
