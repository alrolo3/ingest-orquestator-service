import os
from pathlib import Path

import pytest

from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.elastic.elastic_embedding_dispatcher import (
    ElasticEmbeddingDispatcher,
)
from ingest_orquestator_server.models.embedding_queue import EmbeddingQueueItem


@pytest.mark.skipif(
    os.getenv("INGEST_ELASTIC_INTEGRATION_TESTS") != "true",
    reason="Set INGEST_ELASTIC_INTEGRATION_TESTS=true to run real Elastic smoke tests.",
)
def test_elastic_embedding_submit_smoke(tmp_path: Path) -> None:
    settings = Settings()
    item = _item(tmp_path)

    result = ElasticEmbeddingDispatcher(settings).submit_batch([item])

    assert result.task_id
    assert result.accepted_document_count == 1


def _item(tmp_path: Path) -> EmbeddingQueueItem:
    embedding_input = tmp_path / "embedding_input.jsonl"
    embedding_input.write_text(
        '{"record_id":"smoke-1","document_id":"doc","chunk_id":"c1","text":"smoke"}\n',
        encoding="utf-8",
    )
    return EmbeddingQueueItem(
        queue_id="queue-smoke",
        job_id="job-smoke",
        document_id="doc-smoke",
        source_file_name="smoke.pdf",
        embedding_input_path=embedding_input,
        record_count=1,
    )
