import os
from datetime import UTC, datetime

import pytest

from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.elastic.elastic_chunk_index_dispatch_sink import (
    ElasticChunkIndexDispatchSink,
)
from ingest_orquestator_server.models.parse_diagnostics import ParseDiagnostics
from ingest_orquestator_server.models.parsed_document_content import ParsedDocumentContent
from ingest_orquestator_server.models.parsed_document_dispatch import (
    ParsedDocumentDispatchItem,
)
from ingest_orquestator_server.models.rag_ingestion import RagIngestionRecord


@pytest.mark.skipif(
    os.getenv("INGEST_ELASTIC_INTEGRATION_TESTS") != "true",
    reason="Set INGEST_ELASTIC_INTEGRATION_TESTS=true to run real Elastic smoke tests.",
)
def test_elastic_chunk_index_submit_smoke() -> None:
    settings = Settings()
    item = _item()

    result = ElasticChunkIndexDispatchSink(settings).submit_batch([item])

    assert result.accepted_document_count == 1
    assert result.accepted_record_count == 1
    assert result.raw_response["mode"] == "bulk"


def _item() -> ParsedDocumentDispatchItem:
    record = RagIngestionRecord(
        record_id="smoke-1",
        document_id="doc-smoke",
        job_id="job-smoke",
        content="smoke",
        title="smoke.pdf",
        source_file_name="smoke.pdf",
        input_format="pdf",
        parser="docling",
        pipeline="standard",
        chunk_id="c1",
    )
    return ParsedDocumentDispatchItem(
        queue_id="queue-smoke",
        job_id="job-smoke",
        document_id="doc-smoke",
        source_file_name="smoke.pdf",
        content=ParsedDocumentContent(
            document_id="doc-smoke",
            markdown="smoke",
            metadata={
                "input_format": "pdf",
                "parser": "docling",
                "pipeline": "standard",
            },
            rag_records=[record],
        ),
        diagnostics=ParseDiagnostics(
            parser="docling",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            duration_ms=1,
        ),
        record_count=1,
    )
