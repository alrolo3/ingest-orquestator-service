from pathlib import Path
from typing import Any

from ingest_orquestator_server.application.parser_registry import ParserRegistry
from ingest_orquestator_server.application.services.document_parse_service import (
    DocumentParseService,
)
from ingest_orquestator_server.application.services.parser_chunking_service import (
    ParserChunkingService,
)
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.docling.docling_chunker import DoclingParserChunker
from ingest_orquestator_server.infrastructure.docling.docling_document_parser import (
    DoclingDocumentParser,
)
from ingest_orquestator_server.infrastructure.filesystem.local_parse_output_writer import (
    LocalParseOutputWriter,
)
from ingest_orquestator_server.models.document_element import DocumentElement
from ingest_orquestator_server.models.parse_output import ParseOutput
from ingest_orquestator_server.models.parsed_document import ParsedDocument
from tests.fakes.fake_docling_converter import FakeDoclingConverter


def test_parse_file_can_disable_chunking(tmp_path: Path) -> None:
    input_path = tmp_path / "example.md"
    input_path.write_text("# Example\n", encoding="utf-8")
    settings = Settings(storage_dir=tmp_path, allowed_upload_extensions=[".md"])
    service = _build_service(settings)

    result = service.parse_file(
        file_path=input_path,
        parser_name="docling",
        output_root=tmp_path / "outputs",
        chunking_enabled=False,
    )

    assert len(result.content.rag_records) == 1
    assert result.content.rag_records[0].record_type == "document"
    assert result.outputs.chunks_json is None
    assert result.outputs.embedding_input_jsonl is None
    assert result.outputs.rag_chunks_jsonl is not None
    assert result.diagnostics.metadata["chunking_enabled"] is False


def test_parse_files_uses_docling_batch_path(tmp_path: Path) -> None:
    first = tmp_path / "first.md"
    second = tmp_path / "second.md"
    first.write_text("# First\n", encoding="utf-8")
    second.write_text("# Second\n", encoding="utf-8")
    settings = Settings(storage_dir=tmp_path, allowed_upload_extensions=[".md"])
    service = _build_service(settings)

    results = service.parse_files(
        file_paths=[first, second],
        parser_name="docling",
        output_root=tmp_path / "outputs",
        pipeline="auto",
    )

    assert [result.content.metadata["source_file_name"] for result in results] == [
        "first.md",
        "second.md",
    ]
    assert all(result.outputs.document_metadata_json.exists() for result in results)
    assert all(result.outputs.rag_chunks_jsonl.exists() for result in results)
    assert all(result.diagnostics.metadata["pipeline"] == "standard" for result in results)


def test_parse_file_only_writes_html_when_requested(tmp_path: Path) -> None:
    input_path = tmp_path / "example.md"
    input_path.write_text("# Example\n", encoding="utf-8")
    settings = Settings(storage_dir=tmp_path, allowed_upload_extensions=[".md"])
    service = _build_service(settings)

    without_html = service.parse_file(
        file_path=input_path,
        parser_name="docling",
        output_root=tmp_path / "outputs-no-html",
    )
    with_html = service.parse_file(
        file_path=input_path,
        parser_name="docling",
        output_root=tmp_path / "outputs-html",
        include_html=True,
    )

    assert without_html.content.html is None
    assert without_html.outputs.html is None
    assert with_html.content.html == "<h1>Example</h1>"
    assert with_html.outputs.html is not None


def test_parse_file_passes_ocr_request_options_to_parser(tmp_path: Path) -> None:
    input_path = tmp_path / "example.md"
    input_path.write_text("# Example\n", encoding="utf-8")
    settings = Settings(storage_dir=tmp_path, allowed_upload_extensions=[".md"])
    service = _build_service(settings)

    result = service.parse_file(
        file_path=input_path,
        parser_name="docling",
        output_root=tmp_path / "outputs",
        ocr_languages=["es"],
    )

    assert result.diagnostics.metadata["ocr_engine"] == "suryaocr"
    assert result.diagnostics.metadata["ocr_languages"] == ["es"]


def test_parse_file_adds_selected_chunking_strategy_to_rag_metadata(tmp_path: Path) -> None:
    input_path = tmp_path / "example.md"
    input_path.write_text("# Example\n", encoding="utf-8")
    settings = Settings(storage_dir=tmp_path, allowed_upload_extensions=[".md"])
    service = DocumentParseService(
        parser_registry=ParserRegistry({"docling": lambda: NativeDoclingOutputParser()}),
        output_writer=LocalParseOutputWriter(),
        chunking_service=ParserChunkingService(
            {"docling": DoclingParserChunker(settings)},
            default_enabled=settings.chunking_enabled,
            default_strategy=settings.chunking_strategy,
        ),
    )

    result = service.parse_file(
        file_path=input_path,
        parser_name="docling",
        output_root=tmp_path / "outputs",
        chunking_enabled=True,
        chunking_strategy="page",
    )

    assert result.diagnostics.metadata["chunking_enabled"] is True
    assert result.diagnostics.metadata["chunking_strategy"] == "page"
    assert result.content.rag_records
    assert result.content.rag_records[0].metadata["chunking_strategy"] == "page"


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
        chunking_service=ParserChunkingService(
            {"docling": DoclingParserChunker(settings)},
            default_enabled=settings.chunking_enabled,
            default_strategy=settings.chunking_strategy,
        ),
    )


class NativeDoclingOutputParser:
    name = "docling"

    def parse(
        self,
        file_path: Path,
        *,
        document_id: str | None = None,
        pipeline: str | None = None,
        **_kwargs: Any,
    ) -> ParseOutput:
        from docling_core.types.doc.document import DoclingDocument
        from docling_core.types.doc.labels import DocItemLabel

        resolved_document_id = document_id or "doc-1"
        docling_document = DoclingDocument(name=file_path.stem)
        docling_document.add_text(label=DocItemLabel.PARAGRAPH, text="Example body")
        normalized_document = ParsedDocument(
            document_id=resolved_document_id,
            source_file_name=file_path.name,
            source_path=str(file_path),
            markdown="# Example\n\nExample body",
            text="Example body",
            elements=[
                DocumentElement(
                    element_id="text-1",
                    type="text",
                    page_number=1,
                    text="Example body",
                )
            ],
            metadata={"docling": {"parser": "docling", "input_format": "md"}},
        )
        return ParseOutput(
            document_id=resolved_document_id,
            source_file_name=file_path.name,
            title="Example",
            markdown="# Example\n\nExample body",
            metadata={"input_format": "md", "pipeline": pipeline or "standard"},
            normalized_document=normalized_document,
            chunking_document=docling_document,
        )
