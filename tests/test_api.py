import json
import logging
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
)
from tests.fakes.fake_docling_converter import FakeDoclingConverter


def test_health() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"service": "ingest-orquestator-server", "status": "ok"}


def test_ingest_capabilities_exposes_ui_safe_options(tmp_path: Path) -> None:
    settings = Settings(
        storage_dir=tmp_path,
        allowed_upload_extensions=[".pdf", ".md"],
        docling_allowed_formats=["pdf", "md"],
        docling_pipeline="standard",
        chunking_enabled=True,
        chunking_strategy="hybrid",
        embedding_elastic_password="secret",
    )
    from ingest_orquestator_server.config.settings import get_settings

    app.dependency_overrides[get_settings] = lambda: settings

    try:
        client = TestClient(app)
        response = client.get("/v1/ingest/capabilities")
        assert response.status_code == 200
        body = response.json()
        assert body["default_parser"] == "docling"
        assert body["default_pipeline"] == "standard"
        assert body["allowed_upload_extensions"] == [".md", ".pdf"]
        assert body["chunking"]["default_strategy"] == "hybrid"
        assert {item["value"] for item in body["pipelines"]} == {
            "standard",
            "vlm",
            "auto",
        }
        assert body["runtime"]["ocr_engine"] == settings.docling_pdf_ocr_engine
        assert "secret" not in response.text
        assert "password" not in response.text.lower()
    finally:
        app.dependency_overrides.clear()


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
    dispatch_service = EmbeddingDispatchService(
        settings=settings,
        queue_service=EmbeddingQueueService(max_bulk_size=settings.dispatch_max_bulk_size),
        dispatcher=NoopEmbeddingDispatcher(),
        job_repository=repository,
        output_writer=LocalParseOutputWriter(),
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
    app.dependency_overrides[get_output_retrieval_service] = lambda: OutputRetrievalService(
        repository
    )
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
        assert response.json()["status"] == "parser_queued"
        assert response.json()["source_file_name"] == "example.md"
        assert response.json()["status_url"].endswith(response.json()["job_id"])
        assert response.json()["outputs_url"].endswith(f"{response.json()['job_id']}/outputs")
        job_id = response.json()["job_id"]
        ingestion_service.process_queued_job(job_id)
        ingestion_service.process_embedding_queue()

        job_response = client.get(f"/v1/ingest/jobs/{job_id}")
        assert job_response.status_code == 200
        assert job_response.json()["status"] == "completed"

        jobs_response = client.get(f"/v1/ingest/jobs?ids={job_id},missing")
        assert jobs_response.status_code == 200
        assert [job["job_id"] for job in jobs_response.json()] == [job_id]

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


def test_batch_ingest_persists_valid_jobs_and_rejections(tmp_path: Path) -> None:
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
    dispatch_service = EmbeddingDispatchService(
        settings=settings,
        queue_service=EmbeddingQueueService(max_bulk_size=settings.dispatch_max_bulk_size),
        dispatcher=NoopEmbeddingDispatcher(),
        job_repository=repository,
        output_writer=LocalParseOutputWriter(),
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
            "/v1/ingest/files?pipeline=standard",
            files=[
                ("files", ("example.md", b"# Example", "text/markdown")),
                ("files", ("bad.exe", b"nope", "application/octet-stream")),
            ],
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body["jobs"]) == 1
        assert len(body["failed"]) == 1
        assert body["jobs"][0]["status"] == "parser_queued"
        assert body["failed"][0]["status"] == "failed"
        assert body["failed"][0]["source_file_name"] == "bad.exe"

        failed_job = repository.get(body["failed"][0]["job_id"])
        assert failed_job is not None
        assert failed_job.status == "failed"
        assert failed_job.error is not None
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
    dispatch_service = EmbeddingDispatchService(
        settings=settings,
        queue_service=EmbeddingQueueService(max_bulk_size=settings.dispatch_max_bulk_size),
        dispatcher=NoopEmbeddingDispatcher(),
        job_repository=repository,
        output_writer=LocalParseOutputWriter(),
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


def test_ingest_accepts_chunking_controls(tmp_path: Path) -> None:
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
    dispatch_service = EmbeddingDispatchService(
        settings=settings,
        queue_service=EmbeddingQueueService(max_bulk_size=settings.dispatch_max_bulk_size),
        dispatcher=NoopEmbeddingDispatcher(),
        job_repository=repository,
        output_writer=LocalParseOutputWriter(),
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
    app.dependency_overrides[get_output_retrieval_service] = lambda: OutputRetrievalService(
        repository
    )

    try:
        client = TestClient(app)
        response = client.post(
            "/v1/ingest/file?chunking_enabled=false",
            files={"file": ("example.md", b"# Example", "text/markdown")},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "parser_queued"
        job_id = body["job_id"]
        ingestion_service.process_queued_job(job_id)
        ingestion_service.process_embedding_queue()
        job_response = client.get(f"/v1/ingest/jobs/{job_id}")
        assert job_response.json()["metadata"]["chunking_enabled"] is False
        outputs_response = client.get(f"/v1/ingest/jobs/{job_id}/outputs")
        assert outputs_response.json()["chunks_json"] is None
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
    dispatch_service = EmbeddingDispatchService(
        settings=settings,
        queue_service=EmbeddingQueueService(max_bulk_size=settings.dispatch_max_bulk_size),
        dispatcher=NoopEmbeddingDispatcher(),
        job_repository=repository,
        output_writer=LocalParseOutputWriter(),
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
            "/v1/ingest/file?async_mode=true&pipeline=standard",
            files={"file": ("example.md", b"# Example", "text/markdown")},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "parser_queued"
        job_id = response.json()["job_id"]
        ingestion_service.process_queued_job(job_id)
        ingestion_service.process_embedding_queue()

        job_response = client.get(f"/v1/ingest/jobs/{job_id}")
        assert job_response.status_code == 200
        assert job_response.json()["status"] == "completed"
        assert job_response.json()["metadata"]["pipeline"] == "standard"
    finally:
        app.dependency_overrides.clear()


def test_ingest_file_enqueues_embedding_handoff_internally(
    tmp_path: Path,
    caplog,
) -> None:
    settings = Settings(
        storage_dir=tmp_path,
        allowed_upload_extensions=[".md"],
        dispatch_sink_mode="local_and_elastic",
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
        queue_service=EmbeddingQueueService(max_bulk_size=settings.dispatch_max_bulk_size),
        dispatcher=NoopEmbeddingDispatcher(),
        job_repository=repository,
        output_writer=LocalParseOutputWriter(),
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
    app.dependency_overrides[get_output_retrieval_service] = lambda: OutputRetrievalService(
        repository
    )

    try:
        client = TestClient(app)
        with caplog.at_level(logging.INFO, logger="ingest_orquestator_server.stage"):
            response = client.post(
                "/v1/ingest/file?include_document=false&pipeline=standard",
                files={"file": ("example.md", b"# Example", "text/markdown")},
            )
            job_id = response.json()["job_id"]
            ingestion_service.process_queued_job(job_id)
            ingestion_service.process_embedding_queue()
        assert response.status_code == 200
        assert response.json()["status"] == "parser_queued"

        job_response = client.get(f"/v1/ingest/jobs/{job_id}")
        assert job_response.status_code == 200
        assert job_response.json()["status"] == "completed"
        assert job_response.json()["metadata"]["progress"]["stage"] == "docling.normalize.completed"
        assert job_response.json()["metadata"]["progress_history"]
        assert (
            job_response.json()["metadata"]["dispatch_handoff"]["last_response"][
                "elastic_response"
            ]["mode"]
            == "bulk"
        )

        outputs_response = client.get(f"/v1/ingest/jobs/{job_id}/outputs")
        assert outputs_response.status_code == 200
        assert outputs_response.json()["embedding_input_jsonl"].endswith("embedding_input.jsonl")

        embedding_response = client.get(f"/v1/ingest/jobs/{job_id}/outputs/embedding")
        assert embedding_response.status_code == 200
        assert '"chunk_id"' in embedding_response.text

        events = [
            json.loads(record.message)["event"]
            for record in caplog.records
            if record.name == "ingest_orquestator_server.stage"
        ]
        assert "ingestion.upload.queued" in events
        assert "ingestion.progress" in events
        assert "parser.worker.started" in events
        assert "parser.worker.completed" in events
        assert "dispatch.queue.enqueued" in events
        assert "dispatch.started" in events
        assert "dispatch.completed" in events
    finally:
        app.dependency_overrides.clear()


class NoopEmbeddingDispatcher:
    def submit_batch(self, items: list[EmbeddingQueueItem]) -> EmbeddingDispatchResult:
        return EmbeddingDispatchResult(
            accepted_document_count=len(items),
            raw_response={"mode": "bulk", "successful": len(items)},
        )
