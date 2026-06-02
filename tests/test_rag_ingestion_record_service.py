from ingest_orquestator_server.application.services.rag_ingestion_record_service import (
    RagIngestionRecordService,
)
from ingest_orquestator_server.models import DocumentChunk, ParsedDocument


def test_rag_ingestion_record_service_populates_v3_chunk_contract_fields() -> None:
    document = ParsedDocument(
        document_id="doc-1",
        source_file_name="example.pdf",
        source_path="/tmp/example.pdf",
        title="Original filename title",
        page_count=3,
    )
    chunk = DocumentChunk(
        chunk_id="doc-1:1",
        document_id="doc-1",
        page_start=2,
        page_end=2,
        text="  The useful paragraph.  ",
        metadata={
            "headings": ["Human clean heading"],
            "element_types": ["text"],
            "token_count": 42,
            "chunk_quality": 0.92,
            "searchable": True,
            "boilerplate": False,
            "content_kind": "paragraph",
        },
    )

    records = RagIngestionRecordService().build_records(
        document=document,
        chunks=[chunk],
        job_id="job-1",
        parser="docling",
        pipeline="standard",
        input_format="pdf",
        confidence_summary={"mean_score": 0.95},
        warnings=[],
        chunking_metadata={"chunking_strategy": "token"},
    )

    record = records[0]
    assert record.clean_title == "Human clean heading"
    assert record.headings == ["Human clean heading"]
    assert record.page_count == 3
    assert record.element_types == ["text"]
    assert record.chunking_strategy == "token"
    assert record.searchable is True
    assert record.boilerplate is False
    assert record.content_kind == "paragraph"
    assert record.content_length == len("The useful paragraph.")
    assert record.token_count == 42
    assert record.chunk_quality == 0.92
    assert record.confidence == {"mean_score": 0.95}
    assert "raw_text" not in record.metadata


def test_rag_ingestion_record_service_defaults_v3_quality_controls() -> None:
    document = ParsedDocument(
        document_id="doc-1",
        source_file_name="example.pdf",
        source_path="/tmp/example.pdf",
        title="Example",
    )
    chunk = DocumentChunk(
        chunk_id="doc-1:1",
        document_id="doc-1",
        text="body",
    )

    records = RagIngestionRecordService().build_records(
        document=document,
        chunks=[chunk],
        job_id="job-1",
        parser="docling",
        pipeline="standard",
        input_format="pdf",
        confidence_summary={},
        warnings=[],
        chunking_metadata=None,
    )

    record = records[0]
    assert record.clean_title == "Example"
    assert record.searchable is True
    assert record.boilerplate is False
    assert record.content_kind == "unknown"
    assert record.content_length == 4
