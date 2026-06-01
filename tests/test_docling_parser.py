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

    assert output.normalized_document is not None
    options = output.normalized_document.metadata["docling_options"]
    assert options["common"]["accelerator_device"] == "cuda"
    assert options["common"]["num_threads"] == 8
    assert options["configured_options"]["pdf"]["ocr_batch_size"] == 16
    assert options["runtime"]["stages"]["picture_description"]["resolved_runtime"]
    assert output.normalized_document.metadata["docling"]["input_format"] == "md"
    assert output.normalized_document.metadata["docling"]["pipeline"] == "standard"
    assert "runtime" in output.normalized_document.metadata["docling"]
    assert output.normalized_document.metadata["docling_result"]["status"] is None


def test_parser_emits_docling_progress_updates(tmp_path: Path) -> None:
    input_file = tmp_path / "example.md"
    input_file.write_text("# Example", encoding="utf-8")
    updates = []

    DoclingDocumentParser(converter=FakeDoclingConverter(), settings=Settings()).parse(
        input_file,
        progress_callback=updates.append,
    )

    stages = [update.stage for update in updates]
    assert "docling.input.detected" in stages
    assert "docling.pipeline.resolved" in stages
    assert "docling.convert.started" in stages
    assert "docling.convert.completed" in stages
    assert "docling.normalize.completed" in stages
