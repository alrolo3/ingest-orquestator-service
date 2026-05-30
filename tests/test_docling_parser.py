from pathlib import Path

from ingest_orquestator_server.config import Settings
from ingest_orquestator_server.infrastructure.docling.docling_document_parser import (
    DoclingDocumentParser,
)
from tests.fakes.fake_docling_converter import FakeDoclingConverter


def test_parser_adds_docling_accelerator_metadata(tmp_path: Path) -> None:
    input_file = tmp_path / "example.md"
    input_file.write_text("# Example", encoding="utf-8")
    settings = Settings(
        docling_accelerator_device="cuda",
        docling_num_threads=8,
        docling_pdf_ocr_batch_size=16,
    )

    output = DoclingDocumentParser(converter=FakeDoclingConverter(), settings=settings).parse(
        input_file
    )

    assert output.document.metadata["docling_options"]["accelerator_device"] == "cuda"
    assert output.document.metadata["docling_options"]["num_threads"] == 8
    assert output.document.metadata["docling_options"]["pdf_ocr_batch_size"] == 16
    assert output.document.metadata["docling"]["input_format"] == "md"
    assert output.document.metadata["docling"]["pipeline"] == "standard"
