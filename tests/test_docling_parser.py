from pathlib import Path

from ingest_orquestator_server.config import Settings
from ingest_orquestator_server.parsers.docling_parser import DoclingParser


class FakeConverter:
    def convert(self, source_path: Path) -> object:
        return FakeConversionResult(source_path)


class FakeConversionResult:
    def __init__(self, source_path: Path) -> None:
        self.document = FakeDocument(source_path)


class FakeDocument:
    def __init__(self, source_path: Path) -> None:
        self.source_path = source_path

    def export_to_dict(self) -> dict[str, object]:
        return {
            "name": self.source_path.stem,
            "origin": {"filename": self.source_path.name},
            "pages": {},
            "texts": [],
        }

    def export_to_markdown(self) -> str:
        return "# Example"

    def export_to_text(self) -> str:
        return "Example"

    def export_to_html(self) -> str:
        return "<h1>Example</h1>"


def test_parser_adds_docling_accelerator_metadata(tmp_path: Path) -> None:
    input_file = tmp_path / "example.md"
    input_file.write_text("# Example", encoding="utf-8")
    settings = Settings(
        docling_accelerator_device="cuda",
        docling_num_threads=8,
        docling_pdf_ocr_batch_size=16,
    )

    output = DoclingParser(converter=FakeConverter(), settings=settings).parse(input_file)

    assert output.document.metadata["docling_options"]["accelerator_device"] == "cuda"
    assert output.document.metadata["docling_options"]["num_threads"] == 8
    assert output.document.metadata["docling_options"]["pdf_ocr_batch_size"] == 16
