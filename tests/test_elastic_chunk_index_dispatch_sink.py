from datetime import UTC, datetime
from pathlib import Path

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

    dispatcher = ElasticChunkIndexDispatchSink(
        settings, client=client, bulk_helper=fake_bulk
    )

    result = dispatcher.submit_batch([_item(tmp_path)])

    actions = captured["actions"]
    source = actions[0]["_source"]
    assert result.accepted_document_count == 1
    assert result.accepted_record_count == 1
    assert result.raw_response["mode"] == "bulk"
    assert actions[0]["_index"] == "ingest-embedding-input"
    assert actions[0]["_id"] == "1"
    assert actions[0]["pipeline"] == "embedding-pipeline"
    assert source["content"] == "one"
    assert source["title"] == "Quarterly Revenue"
    assert "content_semantic" not in source
    assert "title_semantic" not in source
    assert source["input_format"] == "pdf"
    assert source["record_type"] == "chunk"
    assert source["page_start"] == 1
    assert source["confidence"] == {"mean_score": 0.95}
    assert source["metadata"]["title"] == "Quarterly Revenue"
    assert "runtime" not in source
    assert "raw_text" not in source
    assert "element_ids" not in source
    assert "source_path" not in source
    assert "raw_text" not in source["metadata"]
    assert "source_path" not in source["metadata"]
    assert captured["kwargs"]["request_timeout"] == 30.0


def test_elastic_dispatcher_uses_semantic_text_v2_without_bulk_action_pipeline(
    tmp_path: Path,
) -> None:
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

    dispatcher = ElasticChunkIndexDispatchSink(
        settings, client=client, bulk_helper=fake_bulk
    )

    result = dispatcher.submit_batch([_item(tmp_path)])

    actions = captured["actions"]
    assert result.raw_response["mapping_version"] == "v2"
    assert actions[0]["_index"] == "open-rag-embeddings-v2"
    assert "pipeline" not in actions[0]
    assert actions[0]["_source"]["content"] == "one"
    assert "content_semantic" not in actions[0]["_source"]
    assert actions[0]["_source"]["title"] == "Quarterly Revenue"
    assert "title_semantic" not in actions[0]["_source"]
    assert set(actions[0]["_source"]) == {
        "record_id",
        "document_id",
        "job_id",
        "chunk_id",
        "record_type",
        "content",
        "source_file_name",
        "title",
        "input_format",
        "parser",
        "pipeline",
        "chunking_strategy",
        "page_start",
        "page_end",
        "confidence",
        "metadata",
    }


class FakeElasticsearchClient:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, dict | None]] = []

    def options(self, **_kwargs):
        return self


def _item(tmp_path: Path) -> ParsedDocumentDispatchItem:
    record = RagIngestionRecord(
        record_id="1",
        document_id="doc",
        job_id="job-1",
        content="one",
        title="Quarterly Revenue",
        source_file_name="sample.pdf",
        input_format="pdf",
        parser="docling",
        pipeline="standard",
        page_start=1,
        page_end=1,
        chunk_id="c1",
        metadata={
            "source_path": str(tmp_path / "private.pdf"),
            "raw_text": "private raw content",
            "title": "Quarterly Revenue",
            "chunking_strategy": "token",
            "confidence_summary": {"mean_score": 0.95},
        },
    )
    return ParsedDocumentDispatchItem(
        queue_id="queue-1",
        job_id="job-1",
        document_id="doc-1",
        source_file_name="sample.pdf",
        content=ParsedDocumentContent(
            document_id="doc",
            markdown="one",
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
