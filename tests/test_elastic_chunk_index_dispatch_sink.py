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


def test_elastic_dispatcher_indexes_v3_contract_without_deprecated_semantic_fields(
    tmp_path: Path,
) -> None:
    settings = Settings(
        embedding_elastic_url="https://elastic.example:9200",
        embedding_elastic_index="open-rag-embeddings-v3",
        embedding_elastic_mapping_version="semantic_text_v3",
        embedding_elastic_pipeline="open_rag_embeddings_v3_multilingual_semantic_pipeline",
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

    action = captured["actions"][0]
    source = action["_source"]
    assert result.raw_response["mapping_version"] == "v3"
    assert action["_index"] == "open-rag-embeddings-v3"
    assert "pipeline" not in action
    assert source["content"] == "one"
    assert source["clean_title"] == "Quarterly Revenue"
    assert source["chunking_strategy"] == "token"
    assert source["content_length"] == 3
    assert source["token_count"] == 1
    assert source["chunk_quality"] == 0.9
    assert source["searchable"] is True
    assert source["boilerplate"] is False
    assert source["content_kind"] == "paragraph"
    assert "content_semantic" not in source
    assert "title_semantic" not in source
    assert "chunker_strategy" not in source


def test_elastic_dispatcher_escapes_v3_semantic_content_template_placeholders(
    tmp_path: Path,
) -> None:
    settings = Settings(
        embedding_elastic_url="https://elastic.example:9200",
        embedding_elastic_index="open-rag-embeddings-v3",
        embedding_elastic_mapping_version="semantic_text_v3",
        embedding_elastic_pipeline="open_rag_embeddings_v3_multilingual_semantic_pipeline",
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

    dispatcher.submit_batch(
        [_item(tmp_path, content="echo ${RED}warning${NC}")]
    )

    source = captured["actions"][0]["_source"]
    assert source["content"] == "echo $ {RED}warning$ {NC}"
    assert source["content_length"] == len("echo $ {RED}warning$ {NC}")


class FakeElasticsearchClient:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, dict | None]] = []

    def options(self, **_kwargs):
        return self


def _item(tmp_path: Path, *, content: str = "one") -> ParsedDocumentDispatchItem:
    record = RagIngestionRecord(
        record_id="1",
        document_id="doc",
        job_id="job-1",
        content=content,
        title="Quarterly Revenue",
        source_file_name="sample.pdf",
        input_format="pdf",
        parser="docling",
        pipeline="standard",
        page_start=1,
        page_end=1,
        chunk_id="c1",
        clean_title="Quarterly Revenue",
        content_length=len(content),
        token_count=1,
        chunk_quality=0.9,
        searchable=True,
        boilerplate=False,
        content_kind="paragraph",
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
            markdown=content,
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
