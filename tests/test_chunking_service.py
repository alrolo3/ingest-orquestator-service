from ingest_orquestator_server.application.services.document_chunking_service import (
    DocumentChunkingService,
)
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.models.document_element import DocumentElement
from ingest_orquestator_server.models.parsed_document import ParsedDocument


def test_chunking_skips_furniture_headers() -> None:
    document = ParsedDocument(
        document_id="doc-1",
        source_file_name="example.pdf",
        source_path="/tmp/example.pdf",
        elements=[
            DocumentElement(
                element_id="header",
                type="page_header",
                page_number=1,
                text="do not embed",
                metadata={"content_layer": "furniture"},
            ),
            DocumentElement(
                element_id="table",
                type="table",
                page_number=1,
                markdown="| A | B |\n| --- | --- |\n| 1 | 2 |",
                metadata={"content_layer": "body"},
            ),
        ],
    )

    chunks = DocumentChunkingService(Settings()).chunk(document)

    assert len(chunks) == 1
    assert chunks[0].text.startswith("| A | B |")
    assert chunks[0].metadata["element_ids"] == ["table"]


def test_chunking_splits_long_text_with_overlap() -> None:
    document = ParsedDocument(
        document_id="doc-1",
        source_file_name="example.pdf",
        source_path="/tmp/example.pdf",
        elements=[
            DocumentElement(
                element_id="text-1",
                type="text",
                page_number=1,
                text="A" * 260,
                metadata={"content_layer": "body"},
            )
        ],
    )
    settings = Settings(chunk_size_chars=100, chunk_overlap_chars=10)

    chunks = DocumentChunkingService(settings).chunk(document)

    assert len(chunks) == 3
    assert all(len(chunk.text) <= 100 for chunk in chunks)


def test_line_based_chunking_uses_docling_chunker() -> None:
    from docling_core.types.doc.document import DoclingDocument
    from docling_core.types.doc.labels import DocItemLabel

    docling_document = DoclingDocument(name="example")
    docling_document.add_heading(text="Intro", level=1)
    docling_document.add_text(
        label=DocItemLabel.PARAGRAPH,
        text="hello world " * 80,
    )
    document = ParsedDocument(
        document_id="doc-1",
        source_file_name="example.md",
        source_path="/tmp/example.md",
        metadata={
            "docling": {
                "parser": "docling",
                "input_format": "md",
                "pipeline": "standard",
            }
        },
    )

    chunks = DocumentChunkingService(Settings(chunk_max_tokens=32)).chunk(
        document,
        docling_document=docling_document,
        chunking_strategy="line_based",
    )

    assert len(chunks) > 1
    assert chunks[0].metadata["chunker_strategy"] == "line_based"
    assert chunks[0].metadata["max_tokens"] == 32
