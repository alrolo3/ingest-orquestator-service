from datetime import UTC, datetime
from pathlib import Path

from ingest_orquestator_server.infrastructure.filesystem.local_parse_output_writer import (
    LocalParseOutputWriter,
)
from ingest_orquestator_server.models import (
    ParsedDocumentContent,
    ParseDiagnostics,
    RagIngestionRecord,
    RagRecordType,
)


def test_write_parse_output_writes_minimal_rag_artifacts(tmp_path: Path) -> None:
    content = ParsedDocumentContent(
        document_id="doc-1",
        markdown="# Hello",
        html="<h1>Hello</h1>",
        metadata={
            "job_id": "job-1",
            "source_file_name": "example.pdf",
            "input_format": "pdf",
            "parser": "docling",
            "pipeline": "standard",
            "page_count": 1,
            "confidence_summary": {"mean_score": 0.94},
            "warnings": [],
        },
        rag_records=[
            RagIngestionRecord(
                record_id="doc-1:rag:1",
                document_id="doc-1",
                job_id="job-1",
                content="Hello",
                title="Example",
                source_file_name="example.pdf",
                input_format="pdf",
                parser="docling",
                pipeline="standard",
                chunk_id="doc-1:1",
                record_type=RagRecordType.CHUNK,
                metadata={"page_count": 1},
            )
        ],
    )
    diagnostics = ParseDiagnostics(
        parser="docling",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        duration_ms=12,
        chunk_count=1,
    )

    outputs = LocalParseOutputWriter().write(content, tmp_path, diagnostics=diagnostics)

    assert outputs.output_dir.exists()
    assert outputs.markdown.read_text(encoding="utf-8") == "# Hello"
    assert outputs.document_metadata_json is not None
    assert '"input_format": "pdf"' in outputs.document_metadata_json.read_text(
        encoding="utf-8"
    )
    assert outputs.rag_chunks_jsonl is not None
    assert '"record_id":"doc-1:rag:1"' in outputs.rag_chunks_jsonl.read_text(
        encoding="utf-8"
    )
    assert outputs.html is not None
    assert outputs.html.read_text(encoding="utf-8") == "<h1>Hello</h1>"
    assert outputs.raw_docling_json is None
    assert outputs.normalized_json is None
    assert outputs.text is None
    assert outputs.embedding_input_jsonl is None
    assert outputs.confidence_json is None
