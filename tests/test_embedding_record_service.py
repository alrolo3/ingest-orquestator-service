from ingest_orquestator_server.application.services.embedding_record_service import (
    EmbeddingRecordService,
)
from ingest_orquestator_server.models import DocumentChunk, ParsedDocument


def test_embedding_records_include_chunk_and_docling_metadata() -> None:
    document = ParsedDocument(
        document_id="doc-1",
        source_file_name="example.pdf",
        source_path="/tmp/example.pdf",
        metadata={
            "docling": {
                "parser": "docling",
                "input_format": "pdf",
                "pipeline": "standard",
                "picture_description_model": "granite_vision",
                "picture_description_runtime": "remote_llm",
                "runtime": {
                    "stages": {
                        "picture_description": {
                            "resolved_runtime": "remote_llm",
                        }
                    }
                },
            }
        },
    )
    chunks = [
        DocumentChunk(
            chunk_id="doc-1:1",
            document_id="doc-1",
            page_start=1,
            page_end=1,
            text="Quarterly Revenue by Product",
            metadata={
                "element_ids": ["pictures/0"],
                "element_types": ["image"],
                "chunker_strategy": "hybrid",
                "raw_text": "Quarterly Revenue by Product",
                "contextualized": True,
            },
        )
    ]

    records = EmbeddingRecordService().build_records(document=document, chunks=chunks)

    assert records[0].record_id == "doc-1:embedding:1"
    assert records[0].metadata["input_format"] == "pdf"
    assert records[0].metadata["pipeline"] == "standard"
    assert records[0].metadata["picture_description_runtime"] == "remote_llm"
    assert (
        records[0].metadata["runtime"]["stages"]["picture_description"]["resolved_runtime"]
        == "remote_llm"
    )
    assert records[0].metadata["element_types"] == ["image"]
    assert records[0].schema_version == "1.3"
    assert records[0].raw_text == "Quarterly Revenue by Product"
    assert records[0].contextualized is True
    assert records[0].metadata["chunker_strategy"] == "hybrid"
