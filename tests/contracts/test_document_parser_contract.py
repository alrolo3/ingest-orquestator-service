from pathlib import Path

from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.docling.docling_document_parser import (
    DoclingDocumentParser,
)
from tests.fakes.fake_docling_converter import FakeDoclingConverter


def assert_document_parser_contract(parser: object, input_file: Path) -> None:
    output = parser.parse(input_file, document_id="doc-1")

    assert output.document.document_id == "doc-1"
    assert output.document.source_file_name == input_file.name
    assert isinstance(output.raw_docling, dict)
    assert isinstance(output.raw_markdown, str)
    assert isinstance(output.raw_text, str)


def test_docling_parser_satisfies_document_parser_contract(tmp_path: Path) -> None:
    input_file = tmp_path / "example.md"
    input_file.write_text("# Example", encoding="utf-8")
    parser = DoclingDocumentParser(converter=FakeDoclingConverter(), settings=Settings())

    assert_document_parser_contract(parser, input_file)
