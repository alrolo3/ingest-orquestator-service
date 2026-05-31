from datetime import UTC, datetime
from pathlib import Path

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
from ingest_orquestator_server.application.services.parser_worker_service import (
    ParserWorkerService,
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
from ingest_orquestator_server.models.embedding_queue import (
    EmbeddingDispatchResult,
    EmbeddingQueueItem,
)
from ingest_orquestator_server.models.ingestion_job import IngestionJob
from ingest_orquestator_server.models.ingestion_status import IngestionStatus
from tests.fakes.fake_docling_converter import FakeDoclingConverter


def test_parser_worker_processes_queued_job_into_dispatch_queue(tmp_path: Path) -> None:
    settings = Settings(storage_dir=tmp_path, allowed_upload_extensions=[".md"])
    repository = SqliteIngestionJobRepository(settings.jobs_db_path)
    input_path = _write_input(tmp_path)
    repository.save(
        IngestionJob(
            job_id="job-1",
            status=IngestionStatus.PARSER_QUEUED,
            parser="docling",
            source_file_name=input_path.name,
            input_path=input_path,
            metadata={"requested_pipeline": "standard"},
        )
    )
    worker = _build_worker(settings, repository)

    try:
        worker.process_job("job-1")
    finally:
        worker.shutdown()

    job = repository.get("job-1")
    assert job is not None
    assert job.status == IngestionStatus.DISPATCH_QUEUED
    assert job.document_id == "job-1"
    assert job.metadata["pipeline"] == "standard"
    assert job.metadata["dispatch_handoff"]["state"] == "dispatch_queued"


def test_parser_worker_marks_missing_input_path_as_failed(tmp_path: Path) -> None:
    settings = Settings(storage_dir=tmp_path)
    repository = SqliteIngestionJobRepository(settings.jobs_db_path)
    repository.save(
        IngestionJob(
            job_id="job-1",
            status=IngestionStatus.PARSER_QUEUED,
            parser="docling",
            source_file_name="missing.md",
        )
    )
    worker = _build_worker(settings, repository)

    try:
        worker.process_job("job-1")
    finally:
        worker.shutdown()

    job = repository.get("job-1")
    assert job is not None
    assert job.status == IngestionStatus.FAILED
    assert job.error == "Queued job has no input path."
    assert job.metadata["error_type"] == "RuntimeError"
    assert job.completed_at is not None


def test_parser_worker_marks_parse_exceptions_as_failed(tmp_path: Path) -> None:
    settings = Settings(storage_dir=tmp_path)
    repository = SqliteIngestionJobRepository(settings.jobs_db_path)
    input_path = _write_input(tmp_path)
    repository.save(
        IngestionJob(
            job_id="job-1",
            status=IngestionStatus.PARSER_QUEUED,
            parser="docling",
            source_file_name=input_path.name,
            input_path=input_path,
        )
    )
    worker = ParserWorkerService(
        settings=settings,
        document_parse_service=FailingDocumentParseService(),
        job_repository=repository,
        dispatch_service=_build_dispatch_service(settings, repository),
    )

    try:
        worker.process_job("job-1")
    finally:
        worker.shutdown()

    job = repository.get("job-1")
    assert job is not None
    assert job.status == IngestionStatus.FAILED
    assert job.error == "parse failed"
    assert job.metadata["error_type"] == "ValueError"


def test_file_ingestion_manual_job_processor_preserves_legacy_dispatch_flow(
    tmp_path: Path,
) -> None:
    settings = Settings(storage_dir=tmp_path, allowed_upload_extensions=[".md"])
    repository = SqliteIngestionJobRepository(settings.jobs_db_path)
    input_path = _write_input(tmp_path)
    repository.save(
        IngestionJob(
            job_id="job-1",
            status=IngestionStatus.PARSER_QUEUED,
            parser="docling",
            source_file_name=input_path.name,
            input_path=input_path,
            metadata={"requested_pipeline": "standard"},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )
    dispatch_service = _build_dispatch_service(settings, repository)
    service = FileIngestionService(
        settings=settings,
        upload_storage=LocalUploadStorage(upload_validator=UploadValidator(settings)),
        document_parse_service=_build_parse_service(settings),
        job_repository=repository,
        upload_validator=UploadValidator(settings),
        embedding_dispatch_service=dispatch_service,
    )

    service.process_queued_job("job-1")
    service.process_embedding_queue()

    job = repository.get("job-1")
    assert job is not None
    assert job.status == IngestionStatus.COMPLETED
    assert job.document_id == "job-1"
    assert job.outputs is not None
    assert job.metadata["pipeline"] == "standard"
    assert job.metadata["dispatch_handoff"]["state"] == "completed"


class FailingDocumentParseService:
    def parse_file(self, **_kwargs):
        raise ValueError("parse failed")


class NoopEmbeddingDispatcher:
    def submit_batch(self, items: list[EmbeddingQueueItem]) -> EmbeddingDispatchResult:
        return EmbeddingDispatchResult(
            accepted_document_count=len(items),
            raw_response={"mode": "bulk", "successful": len(items)},
        )


class ManualEmbeddingDispatchService(EmbeddingDispatchService):
    def notify(self) -> None:
        return None


def _build_worker(
    settings: Settings,
    repository: SqliteIngestionJobRepository,
) -> ParserWorkerService:
    return ParserWorkerService(
        settings=settings,
        document_parse_service=_build_parse_service(settings),
        job_repository=repository,
        dispatch_service=_build_dispatch_service(settings, repository),
    )


def _build_parse_service(settings: Settings) -> DocumentParseService:
    return DocumentParseService(
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


def _build_dispatch_service(
    settings: Settings,
    repository: SqliteIngestionJobRepository,
) -> EmbeddingDispatchService:
    return ManualEmbeddingDispatchService(
        settings=settings,
        queue_service=EmbeddingQueueService(max_bulk_size=settings.dispatch_max_bulk_size),
        dispatcher=NoopEmbeddingDispatcher(),
        job_repository=repository,
        output_writer=LocalParseOutputWriter(),
    )


def _write_input(tmp_path: Path) -> Path:
    input_path = tmp_path / "example.md"
    input_path.write_text("# Example\n", encoding="utf-8")
    return input_path
