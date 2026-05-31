from pathlib import Path

from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.elastic.elastic_embedding_dispatcher import (
    ElasticEmbeddingDispatcher,
)
from ingest_orquestator_server.models.embedding_queue import EmbeddingQueueItem


def test_elastic_dispatcher_uses_client_for_custom_async_endpoint(tmp_path: Path) -> None:
    settings = Settings(
        embedding_elastic_url="https://elastic.example:9200",
        embedding_elastic_submit_path="/_embedding/tasks",
        embedding_elastic_task_id_field="task",
    )
    client = FakeElasticsearchClient({"task": "node:123"})
    dispatcher = ElasticEmbeddingDispatcher(settings, client=client)

    result = dispatcher.submit_batch([_item(tmp_path)])

    assert result.task_id == "node:123"
    method, path, body = client.requests[0]
    assert method == "POST"
    assert path == "/_embedding/tasks"
    assert body is not None
    assert "documents" in body
    assert body["metadata"]["chunk_count"] == 1
    assert body["documents"][0]["record_id"] == "1"
    assert body["documents"][0]["document_id"] == "doc"
    assert body["documents"][0]["chunk_id"] == "c1"
    assert body["documents"][0]["content"] == "one"
    assert body["documents"][0]["title"] == "Quarterly Revenue"
    assert body["documents"][0]["input_format"] == "pdf"
    assert body["documents"][0]["pipeline"] == "standard"
    assert body["documents"][0]["page_start"] == 1
    assert body["documents"][0]["confidence"]["mean_score"] == 0.95
    assert body["documents"][0]["metadata"]["page_start"] == 1
    assert "source_path" not in body["documents"][0]["metadata"]


def test_elastic_dispatcher_uses_bulk_helper_for_bulk_submit(tmp_path: Path) -> None:
    settings = Settings(
        embedding_elastic_url="https://elastic.example:9200",
        embedding_elastic_submit_path="/_bulk",
        embedding_elastic_pipeline="embedding-pipeline",
    )
    client = FakeElasticsearchClient({})
    captured: dict[str, object] = {}

    def fake_bulk(client_arg, actions, **kwargs):
        captured["client"] = client_arg
        captured["actions"] = list(actions)
        captured["kwargs"] = kwargs
        return 1, []

    dispatcher = ElasticEmbeddingDispatcher(settings, client=client, bulk_helper=fake_bulk)

    result = dispatcher.submit_batch([_item(tmp_path)])
    status = dispatcher.get_task_status(result.task_id)

    actions = captured["actions"]
    assert result.task_id.startswith("elastic-bulk:")
    assert result.accepted_document_count == 1
    assert status.completed is True
    assert actions[0]["_index"] == "ingest-embedding-input"
    assert actions[0]["_id"] == "1"
    assert actions[0]["pipeline"] == "embedding-pipeline"
    assert actions[0]["_source"]["content"] == "one"
    assert actions[0]["_source"]["title"] == "Quarterly Revenue"
    assert actions[0]["_source"]["input_format"] == "pdf"
    assert actions[0]["_source"]["metadata"]["page_start"] == 1
    assert "source_path" not in actions[0]["_source"]["metadata"]
    assert captured["kwargs"]["request_timeout"] == 30.0


class FakeElasticsearchClient:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.requests: list[tuple[str, str, dict | None]] = []
        self.tasks = FakeTasksClient()

    def options(self, **_kwargs):
        return self

    def perform_request(self, method: str, path: str, *, body=None, **_kwargs):
        self.requests.append((method, path, body))
        return self.response


class FakeTasksClient:
    def get(self, *, task_id: str):
        return {"completed": True, "task": task_id}


def _item(tmp_path: Path) -> EmbeddingQueueItem:
    embedding_input = tmp_path / "embedding_input.jsonl"
    embedding_input.write_text(
        '{"record_id":"1","document_id":"doc","chunk_id":"c1","text":"one",'
        '"metadata":{"source_path":"/tmp/private.pdf","input_format":"pdf",'
        '"pipeline":"standard","title":"Quarterly Revenue","page_start":1,"page_end":1,'
        '"confidence":{"mean_score":0.95}}}\n',
        encoding="utf-8",
    )
    return EmbeddingQueueItem(
        queue_id="queue-1",
        job_id="job-1",
        document_id="doc-1",
        source_file_name="sample.pdf",
        embedding_input_path=embedding_input,
        record_count=1,
    )
