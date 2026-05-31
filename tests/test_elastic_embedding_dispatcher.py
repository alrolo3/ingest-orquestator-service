from datetime import UTC, datetime
from pathlib import Path

from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.elastic.elastic_embedding_dispatcher import (
    ElasticEmbeddingDispatcher,
)
from ingest_orquestator_server.models.embedding_queue import EmbeddingQueueItem
from ingest_orquestator_server.models.embedding_record import EmbeddingRecord
from ingest_orquestator_server.models.parse_diagnostics import ParseDiagnostics
from ingest_orquestator_server.models.parse_output import ParseOutput
from ingest_orquestator_server.models.parsed_document import ParsedDocument


def test_elastic_dispatcher_uses_bulk_helper_for_bulk_submit(tmp_path: Path) -> None:
    settings = Settings(
        embedding_elastic_url="https://elastic.example:9200",
        embedding_elastic_pipeline="embedding-pipeline",
    )
    client = FakeElasticsearchClient()
    captured: dict[str, object] = {}

    def fake_bulk(client_arg, actions, **kwargs):
        captured["client"] = client_arg
        captured["actions"] = list(actions)
        captured["kwargs"] = kwargs
        return 1, []

    dispatcher = ElasticEmbeddingDispatcher(settings, client=client, bulk_helper=fake_bulk)

    result = dispatcher.submit_batch([_item(tmp_path)])

    actions = captured["actions"]
    assert result.accepted_document_count == 1
    assert result.raw_response["mode"] == "bulk"
    assert actions[0]["_index"] == "ingest-embedding-input"
    assert actions[0]["_id"] == "1"
    assert actions[0]["pipeline"] == "embedding-pipeline"
    assert actions[0]["_source"]["content"] == "one"
    assert actions[0]["_source"]["title"] == "Quarterly Revenue"
    assert "content_semantic" not in actions[0]["_source"]
    assert "title_semantic" not in actions[0]["_source"]
    assert actions[0]["_source"]["input_format"] == "pdf"
    assert actions[0]["_source"]["metadata"]["page_start"] == 1
    assert "source_path" not in actions[0]["_source"]["metadata"]
    assert captured["kwargs"]["request_timeout"] == 30.0


def test_elastic_dispatcher_uses_semantic_text_v2_pipeline(tmp_path: Path) -> None:
    settings = Settings(
        embedding_elastic_url="https://elastic.example:9200",
        embedding_elastic_index="open-rag-embeddings-v2",
        embedding_elastic_mapping_version="semantic_text_v2",
        embedding_elastic_pipeline="open_rag_embeddings_v2_semantic_pipeline",
    )
    client = FakeElasticsearchClient()
    captured: dict[str, object] = {}

    def fake_bulk(client_arg, actions, **kwargs):
        captured["client"] = client_arg
        captured["actions"] = list(actions)
        captured["kwargs"] = kwargs
        return 1, []

    dispatcher = ElasticEmbeddingDispatcher(settings, client=client, bulk_helper=fake_bulk)

    result = dispatcher.submit_batch([_item(tmp_path)])

    actions = captured["actions"]
    assert result.raw_response["mapping_version"] == "v2"
    assert actions[0]["_index"] == "open-rag-embeddings-v2"
    assert actions[0]["pipeline"] == "open_rag_embeddings_v2_semantic_pipeline"
    assert actions[0]["_source"]["content"] == "one"
    assert "content_semantic" not in actions[0]["_source"]
    assert actions[0]["_source"]["title"] == "Quarterly Revenue"
    assert "title_semantic" not in actions[0]["_source"]


class FakeElasticsearchClient:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, dict | None]] = []

    def options(self, **_kwargs):
        return self


def _item(tmp_path: Path) -> EmbeddingQueueItem:
    return EmbeddingQueueItem(
        queue_id="queue-1",
        job_id="job-1",
        document_id="doc-1",
        source_file_name="sample.pdf",
        parse_output=ParseOutput(
            document=ParsedDocument(
                document_id="doc",
                source_file_name="sample.pdf",
                source_path=str(tmp_path / "sample.pdf"),
            ),
            raw_docling={},
            raw_markdown="one",
            raw_text="one",
        ),
        diagnostics=ParseDiagnostics(
            parser="docling",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            duration_ms=1,
        ),
        embedding_records=[
            EmbeddingRecord(
                record_id="1",
                document_id="doc",
                chunk_id="c1",
                text="one",
                metadata={
                    "source_path": "/tmp/private.pdf",
                    "input_format": "pdf",
                    "pipeline": "standard",
                    "title": "Quarterly Revenue",
                    "page_start": 1,
                    "page_end": 1,
                    "confidence": {"mean_score": 0.95},
                },
            )
        ],
        record_count=1,
    )
