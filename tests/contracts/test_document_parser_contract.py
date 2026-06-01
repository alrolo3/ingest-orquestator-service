from pathlib import Path

from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.docling.docling_document_parser import (
    DoclingDocumentParser,
)
from tests.fakes.fake_docling_converter import FakeDoclingConverter


def assert_document_parser_contract(parser: object, input_file: Path) -> None:
    output = parser.parse(input_file, document_id="doc-1")

    assert output.document_id == "doc-1"
    assert output.source_file_name == input_file.name
    assert isinstance(output.markdown, str)
    assert output.html is None
    assert output.normalized_document is not None
    assert output.chunking_document is not None
    assert output.model_dump().get("chunking_document") is None


def test_docling_parser_satisfies_document_parser_contract(tmp_path: Path) -> None:
    input_file = tmp_path / "example.md"
    input_file.write_text("# Example", encoding="utf-8")
    parser = DoclingDocumentParser(converter=FakeDoclingConverter(), settings=Settings())

    assert_document_parser_contract(parser, input_file)
