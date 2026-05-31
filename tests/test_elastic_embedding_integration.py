import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.elastic.elastic_embedding_dispatcher import (
    ElasticEmbeddingDispatcher,
)
from ingest_orquestator_server.models.embedding_queue import EmbeddingQueueItem
from ingest_orquestator_server.models.embedding_record import EmbeddingRecord
from ingest_orquestator_server.models.parse_diagnostics import ParseDiagnostics
from ingest_orquestator_server.models.parse_output import ParseOutput
from ingest_orquestator_server.models.parsed_document import ParsedDocument


@pytest.mark.skipif(
    os.getenv("INGEST_ELASTIC_INTEGRATION_TESTS") != "true",
    reason="Set INGEST_ELASTIC_INTEGRATION_TESTS=true to run real Elastic smoke tests.",
)
def test_elastic_embedding_submit_smoke(tmp_path: Path) -> None:
    settings = Settings()
    item = _item(tmp_path)

    result = ElasticEmbeddingDispatcher(settings).submit_batch([item])

    assert result.accepted_document_count == 1
    assert result.raw_response["mode"] == "bulk"


def _item(tmp_path: Path) -> EmbeddingQueueItem:
    return EmbeddingQueueItem(
        queue_id="queue-smoke",
        job_id="job-smoke",
        document_id="doc-smoke",
        source_file_name="smoke.pdf",
        parse_output=ParseOutput(
            document=ParsedDocument(
                document_id="doc-smoke",
                source_file_name="smoke.pdf",
                source_path=str(tmp_path / "smoke.pdf"),
            ),
            raw_docling={},
            raw_markdown="smoke",
            raw_text="smoke",
        ),
        diagnostics=ParseDiagnostics(
            parser="docling",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            duration_ms=1,
        ),
        embedding_records=[
            EmbeddingRecord(
                record_id="smoke-1",
                document_id="doc-smoke",
                chunk_id="c1",
                text="smoke",
            )
        ],
        record_count=1,
    )
