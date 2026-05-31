from pathlib import Path

from fastapi.testclient import TestClient

from ingest_orquestator_server.api.dependencies import (
    get_file_ingestion_service,
    get_job_query_service,
    get_output_retrieval_service,
)
from ingest_orquestator_server.application.parser_registry import ParserRegistry
from ingest_orquestator_server.application.services.document_chunking_service import (
    DocumentChunkingService,
)
from ingest_orquestator_server.application.services.document_parse_service import (
    DocumentParseService,
)
from ingest_orquestator_server.application.services.embedding_dispatch_service import (
    EmbeddingDispatchService,
)
from ingest_orquestator_server.application.services.embedding_queue_service import (
    EmbeddingQueueService,
)
from ingest_orquestator_server.application.services.file_ingestion_service import (
    FileIngestionService,
)
from ingest_orquestator_server.application.services.job_query_service import JobQueryService
from ingest_orquestator_server.application.services.output_retrieval_service import (
    OutputRetrievalService,
)
from ingest_orquestator_server.application.validation.upload_validator import UploadValidator
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.docling.docling_document_parser import (
    DoclingDocumentParser,
)
from ingest_orquestator_server.infrastructure.filesystem.local_parse_output_writer import (
    LocalParseOutputWriter,
)
from ingest_orquestator_server.infrastructure.filesystem.local_upload_storage import (
    LocalUploadStorage,
)
from ingest_orquestator_server.infrastructure.sqlite.sqlite_ingestion_job_repository import (
    SqliteIngestionJobRepository,
)
from ingest_orquestator_server.main import app
from ingest_orquestator_server.models.embedding_queue import (
    EmbeddingDispatchResult,
    EmbeddingQueueItem,
    EmbeddingTaskStatus,
)
from tests.fakes.fake_docling_converter import FakeDoclingConverter


def test_health() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"service": "ingest-orquestator-server", "status": "ok"}


def test_ingest_job_and_output_endpoints(tmp_path: Path) -> None:
    settings = Settings(storage_dir=tmp_path, allowed_upload_extensions=[".md"])
    repository = SqliteIngestionJobRepository(settings.jobs_db_path)
    validator = UploadValidator(settings)
    parse_service = DocumentParseService(
        parser_registry=ParserRegistry(
            {
                "docling": lambda: DoclingDocumentParser(
                    converter=FakeDoclingConverter(),
                    settings=settings,
                )
            }
        ),
        output_writer=LocalParseOutputWriter(),
        chunking_service=DocumentChunkingService(settings),
    )
    ingestion_service = FileIngestionService(
        settings=settings,
        upload_storage=LocalUploadStorage(upload_validator=validator),
        document_parse_service=parse_service,
        job_repository=repository,
        upload_validator=validator,
    )

    app.dependency_overrides[get_file_ingestion_service] = lambda: ingestion_service
    app.dependency_overrides[get_job_query_service] = lambda: JobQueryService(repository)
    app.dependency_overrides[get_output_retrieval_service] = lambda: OutputRetrievalService(
        repository
    )

    try:
        client = TestClient(app)
        response = client.post(
            "/v1/ingest/file?include_document=false&pipeline=standard",
            files={"file": ("example.md", b"# Example", "text/markdown")},
        )
        assert response.status_code == 200
        job_id = response.json()["job_id"]

        job_response = client.get(f"/v1/ingest/jobs/{job_id}")
        assert job_response.status_code == 200
        assert job_response.json()["status"] == "completed"

        outputs_response = client.get(f"/v1/ingest/jobs/{job_id}/outputs")
        assert outputs_response.status_code == 200
        assert outputs_response.json()["chunks_json"].endswith("chunks.json")
        assert outputs_response.json()["embedding_input_jsonl"].endswith("embedding_input.jsonl")

        chunks_response = client.get(f"/v1/ingest/jobs/{job_id}/outputs/chunks")
        assert chunks_response.status_code == 200
        assert chunks_response.json()["document_id"] == job_id

        embedding_response = client.get(f"/v1/ingest/jobs/{job_id}/outputs/embedding")
        assert embedding_response.status_code == 200
        assert '"chunk_id"' in embedding_response.text
    finally:
        app.dependency_overrides.clear()


def test_ingest_rejects_vlm_pipeline_for_markdown(tmp_path: Path) -> None:
    settings = Settings(storage_dir=tmp_path, allowed_upload_extensions=[".md"])
    repository = SqliteIngestionJobRepository(settings.jobs_db_path)
    validator = UploadValidator(settings)
    parse_service = DocumentParseService(
        parser_registry=ParserRegistry(
            {
                "docling": lambda: DoclingDocumentParser(
                    converter=FakeDoclingConverter(),
                    settings=settings,
                )
            }
        ),
        output_writer=LocalParseOutputWriter(),
        chunking_service=DocumentChunkingService(settings),
    )
    ingestion_service = FileIngestionService(
        settings=settings,
        upload_storage=LocalUploadStorage(upload_validator=validator),
        document_parse_service=parse_service,
        job_repository=repository,
        upload_validator=validator,
    )

    app.dependency_overrides[get_file_ingestion_service] = lambda: ingestion_service

    try:
        client = TestClient(app)
        response = client.post(
            "/v1/ingest/file?pipeline=vlm",
            files={"file": ("example.md", b"# Example", "text/markdown")},
        )
        assert response.status_code == 400
        assert "PDF and image" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_ingest_accepts_profile_and_chunking_controls(tmp_path: Path) -> None:
    settings = Settings(storage_dir=tmp_path, allowed_upload_extensions=[".md"])
    repository = SqliteIngestionJobRepository(settings.jobs_db_path)
    validator = UploadValidator(settings)
    parse_service = DocumentParseService(
        parser_registry=ParserRegistry(
            {
                "docling": lambda: DoclingDocumentParser(
                    converter=FakeDoclingConverter(),
                    settings=settings,
                )
            }
        ),
        output_writer=LocalParseOutputWriter(),
        chunking_service=DocumentChunkingService(settings),
    )
    ingestion_service = FileIngestionService(
        settings=settings,
        upload_storage=LocalUploadStorage(upload_validator=validator),
        document_parse_service=parse_service,
        job_repository=repository,
        upload_validator=validator,
    )

    app.dependency_overrides[get_file_ingestion_service] = lambda: ingestion_service
    app.dependency_overrides[get_job_query_service] = lambda: JobQueryService(repository)

    try:
        client = TestClient(app)
        response = client.post(
            "/v1/ingest/file?profile=parse_only&chunking_enabled=false",
            files={"file": ("example.md", b"# Example", "text/markdown")},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["metadata"]["profile"] == "parse_only"
        assert body["metadata"]["chunking_enabled"] is False
        assert body["outputs"]["chunks_json"] is None
    finally:
        app.dependency_overrides.clear()


def test_async_ingest_queues_and_processes_job(tmp_path: Path) -> None:
    settings = Settings(storage_dir=tmp_path, allowed_upload_extensions=[".md"])
    repository = SqliteIngestionJobRepository(settings.jobs_db_path)
    validator = UploadValidator(settings)
    parse_service = DocumentParseService(
        parser_registry=ParserRegistry(
            {
                "docling": lambda: DoclingDocumentParser(
                    converter=FakeDoclingConverter(),
                    settings=settings,
                )
            }
        ),
        output_writer=LocalParseOutputWriter(),
        chunking_service=DocumentChunkingService(settings),
    )
    ingestion_service = FileIngestionService(
        settings=settings,
        upload_storage=LocalUploadStorage(upload_validator=validator),
        document_parse_service=parse_service,
        job_repository=repository,
        upload_validator=validator,
    )

    app.dependency_overrides[get_file_ingestion_service] = lambda: ingestion_service
    app.dependency_overrides[get_job_query_service] = lambda: JobQueryService(repository)

    try:
        client = TestClient(app)
        response = client.post(
            "/v1/ingest/file?async_mode=true&pipeline=standard",
            files={"file": ("example.md", b"# Example", "text/markdown")},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "queued"
        job_id = response.json()["job_id"]

        job_response = client.get(f"/v1/ingest/jobs/{job_id}")
        assert job_response.status_code == 200
        assert job_response.json()["status"] == "completed"
        assert job_response.json()["metadata"]["pipeline"] == "standard"
    finally:
        app.dependency_overrides.clear()


def test_ingest_file_enqueues_embedding_handoff_internally(tmp_path: Path) -> None:
    settings = Settings(
        storage_dir=tmp_path,
        allowed_upload_extensions=[".md"],
        embedding_queue_enabled=True,
        embedding_elastic_task_poll_interval_seconds=0.001,
    )
    repository = SqliteIngestionJobRepository(settings.jobs_db_path)
    validator = UploadValidator(settings)
    parse_service = DocumentParseService(
        parser_registry=ParserRegistry(
            {
                "docling": lambda: DoclingDocumentParser(
                    converter=FakeDoclingConverter(),
                    settings=settings,
                )
            }
        ),
        output_writer=LocalParseOutputWriter(),
        chunking_service=DocumentChunkingService(settings),
    )
    dispatch_service = EmbeddingDispatchService(
        settings=settings,
        queue_service=EmbeddingQueueService(max_bulk_size=settings.embedding_queue_max_bulk_size),
        dispatcher=NoopEmbeddingDispatcher(),
        job_repository=repository,
    )
    ingestion_service = FileIngestionService(
        settings=settings,
        upload_storage=LocalUploadStorage(upload_validator=validator),
        document_parse_service=parse_service,
        job_repository=repository,
        upload_validator=validator,
        embedding_dispatch_service=dispatch_service,
    )

    app.dependency_overrides[get_file_ingestion_service] = lambda: ingestion_service
    app.dependency_overrides[get_job_query_service] = lambda: JobQueryService(repository)

    try:
        client = TestClient(app)
        response = client.post(
            "/v1/ingest/file?include_document=false&pipeline=standard",
            files={"file": ("example.md", b"# Example", "text/markdown")},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "embedding_queued"
        job_id = response.json()["job_id"]

        job_response = client.get(f"/v1/ingest/jobs/{job_id}")
        assert job_response.status_code == 200
        assert job_response.json()["status"] == "embedding_completed"
        assert job_response.json()["metadata"]["embedding_handoff"]["task_id"] == "task-1"
    finally:
        app.dependency_overrides.clear()


class NoopEmbeddingDispatcher:
    def submit_batch(self, items: list[EmbeddingQueueItem]) -> EmbeddingDispatchResult:
        return EmbeddingDispatchResult(
            task_id="task-1",
            accepted_document_count=len(items),
            raw_response={"task": "task-1"},
        )

    def get_task_status(self, task_id: str) -> EmbeddingTaskStatus:
        return EmbeddingTaskStatus(task_id=task_id, completed=True)
