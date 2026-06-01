import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from ingest_orquestator_server.api.dependencies import (
    get_file_ingestion_service,
    get_job_query_service,
    get_job_removal_service,
    get_output_retrieval_service,
    get_queue_metrics_service,
)
from ingest_orquestator_server.application.parser_registry import ParserRegistry
from ingest_orquestator_server.application.services.document_parse_service import (
    DocumentParseService,
)
from ingest_orquestator_server.application.services.file_ingestion_service import (
    FileIngestionService,
)
from ingest_orquestator_server.application.services.job_query_service import JobQueryService
from ingest_orquestator_server.application.services.job_removal_service import (
    JobRemovalService,
)
from ingest_orquestator_server.application.services.output_retrieval_service import (
    OutputRetrievalService,
)
from ingest_orquestator_server.application.services.parsed_document_dispatch_queue_service import (
    ParsedDocumentDispatchQueueService,
)
from ingest_orquestator_server.application.services.parsed_document_dispatch_service import (
    ParsedDocumentDispatchService,
)
from ingest_orquestator_server.application.services.queue_metrics_service import (
    QueueMetricsService,
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
from ingest_orquestator_server.infrastructure.parser.parser_chunking_factory import (
    build_parser_chunking_service,
)
from ingest_orquestator_server.infrastructure.sqlite.sqlite_ingestion_job_repository import (
    SqliteIngestionJobRepository,
)
from ingest_orquestator_server.main import app
from ingest_orquestator_server.models.ingestion_job import IngestionJob
from ingest_orquestator_server.models.ingestion_status import IngestionStatus
from ingest_orquestator_server.models.parsed_document_dispatch import (
    DispatchSinkResult,
    ParsedDocumentDispatchItem,
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
        docling_pipeline="standard",
        chunking_enabled=False,
        chunking_strategy="page",
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
        assert body["chunking"]["enabled"] is False
        assert body["chunking"]["default_strategy"] == "page"
        assert [item["value"] for item in body["parsers"][0]["chunking"]["strategies"]] == [
            "token",
            "page",
        ]
        assert body["chunking"]["by_parser"]["docling"]["default_strategy"] == "page"
        assert {item["value"] for item in body["pipelines"]} == {
            "standard",
            "vlm",
            "auto",
        }
        assert body["runtime"]["ocr_engine"] == settings.docling_pdf_ocr_engine
        assert body["output_types"] == ["metadata", "markdown", "rag", "html"]
        assert "secret" not in response.text
        assert "password" not in response.text.lower()
    finally:
        app.dependency_overrides.clear()


def test_ingestor_settings_api_persists_overrides_and_updates_capabilities(tmp_path: Path) -> None:
    settings = Settings(
        storage_dir=tmp_path,
        max_upload_size_mb=100,
        docling_accelerator_device="cpu",
        embedding_elastic_password="env-secret",
    )
    from ingest_orquestator_server.config.settings import get_settings

    app.dependency_overrides[get_settings] = lambda: settings

    try:
        client = TestClient(app)
        response = client.patch(
            "/v1/ingest/settings",
            json={
                "values": {
                    "docling_accelerator_device": "cuda",
                    "max_upload_size_mb": 256,
                    "embedding_elastic_password": "sqlite-secret",
                }
            },
        )
        assert response.status_code == 200
        body = response.json()
        fields_by_key = {field["key"]: field for field in body["fields"]}
        assert fields_by_key["docling_accelerator_device"]["value"] == "cuda"
        assert fields_by_key["docling_accelerator_device"]["source"] == "sqlite"
        assert fields_by_key["embedding_elastic_password"]["value"] is None
        assert fields_by_key["embedding_elastic_password"]["configured"] is True
        assert "sqlite-secret" not in response.text

        capabilities = client.get("/v1/ingest/capabilities").json()
        assert capabilities["max_upload_size_mb"] == 256
        assert capabilities["runtime"]["docling_accelerator_device"] == "cuda"

        reset_response = client.patch(
            "/v1/ingest/settings",
            json={"reset_keys": ["docling_accelerator_device"]},
        )
        reset_fields = {field["key"]: field for field in reset_response.json()["fields"]}
        assert reset_fields["docling_accelerator_device"]["value"] == "cpu"
        assert reset_fields["docling_accelerator_device"]["source"] == "env"
    finally:
        app.dependency_overrides.clear()


def test_ingestor_settings_api_rejects_invalid_runtime_setting(tmp_path: Path) -> None:
    settings = Settings(storage_dir=tmp_path)
    from ingest_orquestator_server.config.settings import get_settings

    app.dependency_overrides[get_settings] = lambda: settings

    try:
        client = TestClient(app)
        response = client.patch(
            "/v1/ingest/settings",
            json={"values": {"docling_accelerator_device": "gpu"}},
        )

        assert response.status_code == 400
        assert "docling_accelerator_device" in response.text
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
        chunking_service=build_parser_chunking_service(settings),
    )
    dispatch_service = ParsedDocumentDispatchService(
        settings=settings,
        queue_service=ParsedDocumentDispatchQueueService(
            max_bulk_size=settings.dispatch_max_bulk_size
        ),
        dispatcher=NoopParsedDocumentDispatchSink(),
        job_repository=repository,
        output_writer=LocalParseOutputWriter(),
    )
    ingestion_service = FileIngestionService(
        settings=settings,
        upload_storage=LocalUploadStorage(upload_validator=validator),
        document_parse_service=parse_service,
        job_repository=repository,
        upload_validator=validator,
        parsed_document_dispatch_service=dispatch_service,
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
        assert response.json()["status"] == "parser_queued"
        assert response.json()["source_file_name"] == "example.md"
        assert response.json()["status_url"].endswith(response.json()["job_id"])
        assert response.json()["outputs_url"].endswith(f"{response.json()['job_id']}/outputs")
        job_id = response.json()["job_id"]
        ingestion_service.process_queued_job(job_id)
        ingestion_service.process_dispatch_queue()

        job_response = client.get(f"/v1/ingest/jobs/{job_id}")
        assert job_response.status_code == 200
        assert job_response.json()["status"] == "completed"

        jobs_response = client.get(f"/v1/ingest/jobs?ids={job_id},missing")
        assert jobs_response.status_code == 200
        assert [job["job_id"] for job in jobs_response.json()] == [job_id]

        outputs_response = client.get(f"/v1/ingest/jobs/{job_id}/outputs")
        assert outputs_response.status_code == 200
        assert outputs_response.json()["document_metadata_json"].endswith(
            "document_metadata.json"
        )
        assert outputs_response.json()["rag_chunks_jsonl"].endswith("rag_chunks.jsonl")
        assert outputs_response.json()["raw_docling_json"] is None
        assert outputs_response.json()["normalized_json"] is None
        assert outputs_response.json()["text"] is None

        rag_response = client.get(f"/v1/ingest/jobs/{job_id}/outputs/rag")
        assert rag_response.status_code == 200
        assert '"document_id":"' in rag_response.text

        legacy_embedding_response = client.get(
            f"/v1/ingest/jobs/{job_id}/outputs/embedding"
        )
        assert legacy_embedding_response.status_code == 404
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
        chunking_service=build_parser_chunking_service(settings),
    )
    dispatch_service = ParsedDocumentDispatchService(
        settings=settings,
        queue_service=ParsedDocumentDispatchQueueService(
            max_bulk_size=settings.dispatch_max_bulk_size
        ),
        dispatcher=NoopParsedDocumentDispatchSink(),
        job_repository=repository,
        output_writer=LocalParseOutputWriter(),
    )
    ingestion_service = FileIngestionService(
        settings=settings,
        upload_storage=LocalUploadStorage(upload_validator=validator),
        document_parse_service=parse_service,
        job_repository=repository,
        upload_validator=validator,
        parsed_document_dispatch_service=dispatch_service,
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
        chunking_service=build_parser_chunking_service(settings),
    )
    dispatch_service = ParsedDocumentDispatchService(
        settings=settings,
        queue_service=ParsedDocumentDispatchQueueService(
            max_bulk_size=settings.dispatch_max_bulk_size
        ),
        dispatcher=NoopParsedDocumentDispatchSink(),
        job_repository=repository,
        output_writer=LocalParseOutputWriter(),
    )
    ingestion_service = FileIngestionService(
        settings=settings,
        upload_storage=LocalUploadStorage(upload_validator=validator),
        document_parse_service=parse_service,
        job_repository=repository,
        upload_validator=validator,
        parsed_document_dispatch_service=dispatch_service,
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


def test_ingest_rejects_unsupported_chunking_strategy_before_queueing(
    tmp_path: Path,
) -> None:
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
        chunking_service=build_parser_chunking_service(settings),
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
            "/v1/ingest/file?chunking_enabled=true&chunking_strategy=line",
            files={"file": ("example.md", b"# Example", "text/markdown")},
        )

        assert response.status_code == 400
        assert "does not support" in response.json()["detail"]
        assert repository.list_active_job_ids() == set()
    finally:
        app.dependency_overrides.clear()


def test_ingest_persists_request_level_chunking_options(tmp_path: Path) -> None:
    settings = Settings(
        storage_dir=tmp_path,
        allowed_upload_extensions=[".md"],
        chunking_enabled=False,
        chunking_strategy="page",
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
        chunking_service=build_parser_chunking_service(settings),
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
            "/v1/ingest/file?chunking_enabled=true&chunking_strategy=page",
            files={"file": ("example.md", b"# Example", "text/markdown")},
        )

        assert response.status_code == 200
        stored_job = repository.get(response.json()["job_id"])
        assert stored_job is not None
        assert stored_job.metadata["requested_chunking_enabled"] is True
        assert stored_job.metadata["requested_chunking_strategy"] == "page"
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
        chunking_service=build_parser_chunking_service(settings),
    )
    dispatch_service = ParsedDocumentDispatchService(
        settings=settings,
        queue_service=ParsedDocumentDispatchQueueService(
            max_bulk_size=settings.dispatch_max_bulk_size
        ),
        dispatcher=NoopParsedDocumentDispatchSink(),
        job_repository=repository,
        output_writer=LocalParseOutputWriter(),
    )
    ingestion_service = FileIngestionService(
        settings=settings,
        upload_storage=LocalUploadStorage(upload_validator=validator),
        document_parse_service=parse_service,
        job_repository=repository,
        upload_validator=validator,
        parsed_document_dispatch_service=dispatch_service,
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
        ingestion_service.process_dispatch_queue()
        job_response = client.get(f"/v1/ingest/jobs/{job_id}")
        assert job_response.json()["metadata"]["chunking_enabled"] is False
        outputs_response = client.get(f"/v1/ingest/jobs/{job_id}/outputs")
        assert outputs_response.json()["chunks_json"] is None
        assert outputs_response.json()["rag_chunks_jsonl"].endswith("rag_chunks.jsonl")
        rag_response = client.get(f"/v1/ingest/jobs/{job_id}/outputs/rag")
        assert rag_response.status_code == 200
        assert '"record_type":"document"' in rag_response.text
    finally:
        app.dependency_overrides.clear()


def test_ingest_accepts_dispatcher_and_ocr_controls(tmp_path: Path) -> None:
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
        chunking_service=build_parser_chunking_service(settings),
    )
    dispatch_service = ParsedDocumentDispatchService(
        settings=settings,
        queue_service=ParsedDocumentDispatchQueueService(
            max_bulk_size=settings.dispatch_max_bulk_size
        ),
        dispatcher=NoopParsedDocumentDispatchSink(),
        job_repository=repository,
        output_writer=LocalParseOutputWriter(),
    )
    ingestion_service = FileIngestionService(
        settings=settings,
        upload_storage=LocalUploadStorage(upload_validator=validator),
        document_parse_service=parse_service,
        job_repository=repository,
        upload_validator=validator,
        parsed_document_dispatch_service=dispatch_service,
    )

    app.dependency_overrides[get_file_ingestion_service] = lambda: ingestion_service

    try:
        client = TestClient(app)
        response = client.post(
            "/v1/ingest/file?dispatch_sink_mode=elastic&ocr_languages=es"
            "&pipeline=standard&include_html=true",
            files={"file": ("example.md", b"# Example", "text/markdown")},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["metadata"]["requested_dispatch_sink_mode"] == "elastic"
        assert body["metadata"]["requested_ocr_languages"] == ["es"]
        assert body["metadata"]["requested_include_html"] is True

        stored_job = repository.get(body["job_id"])
        assert stored_job is not None
        assert stored_job.metadata["requested_dispatch_sink_mode"] == "elastic"
        assert stored_job.metadata["requested_ocr_languages"] == ["es"]
        assert stored_job.metadata["requested_include_html"] is True
    finally:
        app.dependency_overrides.clear()


def test_ingest_ocr_language_api_param_controls_parser_options(tmp_path: Path) -> None:
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
        chunking_service=build_parser_chunking_service(settings),
    )
    dispatch_service = ParsedDocumentDispatchService(
        settings=settings,
        queue_service=ParsedDocumentDispatchQueueService(
            max_bulk_size=settings.dispatch_max_bulk_size
        ),
        dispatcher=NoopParsedDocumentDispatchSink(),
        job_repository=repository,
        output_writer=LocalParseOutputWriter(),
    )
    ingestion_service = FileIngestionService(
        settings=settings,
        upload_storage=LocalUploadStorage(upload_validator=validator),
        document_parse_service=parse_service,
        job_repository=repository,
        upload_validator=validator,
        parsed_document_dispatch_service=dispatch_service,
    )

    app.dependency_overrides[get_file_ingestion_service] = lambda: ingestion_service
    app.dependency_overrides[get_job_query_service] = lambda: JobQueryService(repository)

    try:
        client = TestClient(app)
        response = client.post(
            "/v1/ingest/file?ocr_languages=es",
            files={"file": ("example.md", b"# Example", "text/markdown")},
        )
        assert response.status_code == 200
        job_id = response.json()["job_id"]

        ingestion_service.process_queued_job(job_id)
        job_response = client.get(f"/v1/ingest/jobs/{job_id}")

        assert job_response.status_code == 200
        metadata = job_response.json()["metadata"]
        assert metadata["requested_ocr_languages"] == ["es"]
        assert metadata["ocr_engine"] == "suryaocr"
        assert metadata["ocr_languages"] == ["es"]
    finally:
        app.dependency_overrides.clear()


def test_ingest_rejects_invalid_dispatcher_and_ocr_controls(tmp_path: Path) -> None:
    settings = Settings(storage_dir=tmp_path, allowed_upload_extensions=[".md"])
    repository = SqliteIngestionJobRepository(settings.jobs_db_path)
    validator = UploadValidator(settings)
    ingestion_service = FileIngestionService(
        settings=settings,
        upload_storage=LocalUploadStorage(upload_validator=validator),
        document_parse_service=DocumentParseService(
            parser_registry=ParserRegistry(
                {
                    "docling": lambda: DoclingDocumentParser(
                        converter=FakeDoclingConverter(),
                        settings=settings,
                    )
                }
            ),
            output_writer=LocalParseOutputWriter(),
            chunking_service=build_parser_chunking_service(settings),
        ),
        job_repository=repository,
        upload_validator=validator,
    )

    app.dependency_overrides[get_file_ingestion_service] = lambda: ingestion_service

    try:
        client = TestClient(app)
        bad_dispatcher = client.post(
            "/v1/ingest/file?dispatch_sink_mode=shell",
            files={"file": ("example.md", b"# Example", "text/markdown")},
        )
        bad_ocr = client.post(
            "/v1/ingest/file?ocr_languages=../../etc/passwd",
            files={"file": ("example.md", b"# Example", "text/markdown")},
        )
        assert bad_dispatcher.status_code == 400
        assert "dispatch_sink_mode" in bad_dispatcher.json()["detail"]
        assert bad_ocr.status_code == 400
        assert "ocr_languages" in bad_ocr.json()["detail"]
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
        chunking_service=build_parser_chunking_service(settings),
    )
    dispatch_service = ParsedDocumentDispatchService(
        settings=settings,
        queue_service=ParsedDocumentDispatchQueueService(
            max_bulk_size=settings.dispatch_max_bulk_size
        ),
        dispatcher=NoopParsedDocumentDispatchSink(),
        job_repository=repository,
        output_writer=LocalParseOutputWriter(),
    )
    ingestion_service = FileIngestionService(
        settings=settings,
        upload_storage=LocalUploadStorage(upload_validator=validator),
        document_parse_service=parse_service,
        job_repository=repository,
        upload_validator=validator,
        parsed_document_dispatch_service=dispatch_service,
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
        ingestion_service.process_dispatch_queue()

        job_response = client.get(f"/v1/ingest/jobs/{job_id}")
        assert job_response.status_code == 200
        assert job_response.json()["status"] == "completed"
        assert job_response.json()["metadata"]["pipeline"] == "standard"
    finally:
        app.dependency_overrides.clear()


def test_ingest_file_enqueues_parsed_document_handoff_internally(
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
        chunking_service=build_parser_chunking_service(settings),
    )
    dispatch_service = ParsedDocumentDispatchService(
        settings=settings,
        queue_service=ParsedDocumentDispatchQueueService(
            max_bulk_size=settings.dispatch_max_bulk_size
        ),
        dispatcher=NoopParsedDocumentDispatchSink(),
        job_repository=repository,
        output_writer=LocalParseOutputWriter(),
    )
    ingestion_service = FileIngestionService(
        settings=settings,
        upload_storage=LocalUploadStorage(upload_validator=validator),
        document_parse_service=parse_service,
        job_repository=repository,
        upload_validator=validator,
        parsed_document_dispatch_service=dispatch_service,
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
            ingestion_service.process_dispatch_queue()
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
        assert outputs_response.json()["rag_chunks_jsonl"].endswith("rag_chunks.jsonl")

        rag_response = client.get(f"/v1/ingest/jobs/{job_id}/outputs/rag")
        assert rag_response.status_code == 200
        assert '"chunk_id"' in rag_response.text

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


def test_queue_metrics_endpoint_reports_persisted_job_stages(tmp_path: Path) -> None:
    settings = Settings(
        storage_dir=tmp_path,
        parser_process_count=4,
        parser_threads_per_process=1,
        dispatch_worker_count=3,
    )
    repository = SqliteIngestionJobRepository(settings.jobs_db_path)
    repository.save(
        IngestionJob(
            job_id="parser-1",
            status=IngestionStatus.PARSER_QUEUED,
            parser="docling",
            source_file_name="parser.pdf",
        )
    )
    repository.save(
        IngestionJob(
            job_id="active-parser-1",
            status=IngestionStatus.PARSING,
            parser="docling",
            source_file_name="active.pdf",
        )
    )
    repository.save(
        IngestionJob(
            job_id="stale-parser-1",
            status=IngestionStatus.PARSING,
            parser="docling",
            source_file_name="stale.pdf",
            updated_at=datetime.now(UTC)
            - timedelta(milliseconds=settings.dramatiq_parser_time_limit_ms + 1),
        )
    )
    repository.save(
        IngestionJob(
            job_id="dispatch-1",
            status=IngestionStatus.DISPATCH_QUEUED,
            parser="docling",
            source_file_name="dispatch.pdf",
        )
    )
    repository.save(
        IngestionJob(
            job_id="done-1",
            status=IngestionStatus.COMPLETED,
            parser="docling",
            source_file_name="done.pdf",
        )
    )
    app.dependency_overrides[get_queue_metrics_service] = lambda: QueueMetricsService(
        settings=settings,
        job_repository=repository,
        dispatch_service=None,
    )

    try:
        client = TestClient(app)
        response = client.get("/v1/ingest/queue/metrics?limit=5")

        assert response.status_code == 200
        body = response.json()
        stages = {stage["name"]: stage for stage in body["stages"]}
        assert body["queue_backend"] == "local"
        assert body["parser_process_count"] == 4
        assert body["parser_threads_per_process"] == 1
        assert body["parser_worker_count"] == 4
        assert body["dispatch_worker_count"] == 3
        assert body["active_parser_job_count"] == 2
        assert body["queued_parser_job_count"] == 1
        assert body["stale_parser_job_count"] == 1
        assert body["status_counts"]["parser_queued"] == 1
        assert stages["parser_queue"]["count"] == 1
        assert stages["active_parser_jobs"]["count"] == 2
        assert stages["dispatch_queue"]["count"] == 1
        assert stages["dispatch_queue"]["jobs"][0]["job_id"] == "dispatch-1"
        assert stages["processed"]["count"] == 1
    finally:
        app.dependency_overrides.clear()


def test_delete_job_endpoint_removes_job(tmp_path: Path) -> None:
    settings = Settings(storage_dir=tmp_path)
    repository = SqliteIngestionJobRepository(settings.jobs_db_path)
    repository.save(
        IngestionJob(
            job_id="job-1",
            status=IngestionStatus.PARSER_QUEUED,
            parser="docling",
            source_file_name="example.pdf",
        )
    )
    app.dependency_overrides[get_job_removal_service] = lambda: JobRemovalService(
        settings=settings,
        job_repository=repository,
    )
    app.dependency_overrides[get_job_query_service] = lambda: JobQueryService(repository)

    try:
        client = TestClient(app)
        response = client.delete("/v1/ingest/jobs/job-1")

        assert response.status_code == 200
        body = response.json()
        assert body["job_id"] == "job-1"
        assert body["previous_status"] == "parser_queued"
        assert body["removed"] is True
        assert repository.get("job-1") is None
        assert client.get("/v1/ingest/jobs/job-1").status_code == 404
        assert client.delete("/v1/ingest/jobs/missing").status_code == 404
    finally:
        app.dependency_overrides.clear()


class NoopParsedDocumentDispatchSink:
    def submit_batch(self, items: list[ParsedDocumentDispatchItem]) -> DispatchSinkResult:
        accepted_record_count = sum(len(item.content.rag_records) for item in items)
        return DispatchSinkResult(
            accepted_document_count=len(items),
            accepted_record_count=accepted_record_count,
            raw_response={"mode": "bulk", "successful": accepted_record_count},
        )
