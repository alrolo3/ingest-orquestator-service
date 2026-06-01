from datetime import UTC, datetime
from pathlib import Path

import pytest

from ingest_orquestator_server.application.parser_registry import ParserRegistry
from ingest_orquestator_server.application.services.document_parse_service import (
    DocumentParseResult,
    DocumentParseService,
)
from ingest_orquestator_server.application.services.file_ingestion_service import (
    FileIngestionService,
)
from ingest_orquestator_server.application.services.parsed_document_dispatch_queue_service import (
    ParsedDocumentDispatchQueueService,
)
from ingest_orquestator_server.application.services.parsed_document_dispatch_service import (
    ParsedDocumentDispatchService,
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
from ingest_orquestator_server.infrastructure.parser.parser_chunking_factory import (
    build_parser_chunking_service,
)
from ingest_orquestator_server.infrastructure.sqlite.sqlite_ingestion_job_repository import (
    SqliteIngestionJobRepository,
)
from ingest_orquestator_server.models.ingestion_job import IngestionJob
from ingest_orquestator_server.models.ingestion_status import IngestionStatus
from ingest_orquestator_server.models.parse_diagnostics import ParseDiagnostics
from ingest_orquestator_server.models.parsed_document_content import ParsedDocumentContent
from ingest_orquestator_server.models.parsed_document_dispatch import (
    DispatchSinkResult,
    ParsedDocumentDispatchItem,
)
from ingest_orquestator_server.models.rag_ingestion import RagIngestionRecord
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


def test_parser_worker_passes_requested_ocr_languages(tmp_path: Path) -> None:
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
            metadata={
                "requested_pipeline": "standard",
                "requested_ocr_languages": ["es"],
            },
        )
    )
    parse_service = RecordingDocumentParseService(tmp_path)
    worker = ParserWorkerService(
        settings=settings,
        document_parse_service=parse_service,
        job_repository=repository,
        dispatch_service=_build_dispatch_service(settings, repository),
    )

    try:
        worker.process_job("job-1")
    finally:
        worker.shutdown()

    assert parse_service.calls[0]["ocr_languages"] == ["es"]


def test_parser_worker_passes_requested_html_output(tmp_path: Path) -> None:
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
            metadata={
                "requested_pipeline": "standard",
                "requested_include_html": True,
            },
        )
    )
    parse_service = RecordingDocumentParseService(tmp_path)
    worker = ParserWorkerService(
        settings=settings,
        document_parse_service=parse_service,
        job_repository=repository,
        dispatch_service=_build_dispatch_service(settings, repository),
    )

    try:
        worker.process_job("job-1")
    finally:
        worker.shutdown()

    assert parse_service.calls[0]["include_html"] is True


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
    settings = Settings(storage_dir=tmp_path, parser_max_retry_attempts=2)
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
        first_result = worker.process_job("job-1")
        second_result = worker.process_job("job-1")
        third_result = worker.process_job("job-1")
    finally:
        worker.shutdown()

    job = repository.get("job-1")
    assert job is not None
    assert first_result.retry_requested is True
    assert second_result.retry_requested is True
    assert third_result.retry_requested is False
    assert job.status == IngestionStatus.FAILED
    assert job.error == "parse failed"
    assert job.metadata["error_type"] == "ValueError"
    assert job.metadata["parser_retry"] == {
        "state": "exhausted",
        "failure_count": 3,
        "max_retries": 2,
        "last_error": "parse failed",
        "last_error_type": "ValueError",
    }


def test_parser_worker_marks_retrying_job_before_retry_limit(
    tmp_path: Path,
) -> None:
    settings = Settings(storage_dir=tmp_path, parser_max_retry_attempts=2)
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
        result = worker.process_job("job-1")
    finally:
        worker.shutdown()

    job = repository.get("job-1")
    assert job is not None
    assert result.retry_requested is True
    assert job.status == IngestionStatus.RETRYING
    assert job.completed_at is None
    assert job.error == "parse failed"
    assert job.metadata["parser_retry"] == {
        "state": "retrying",
        "failure_count": 1,
        "max_retries": 2,
        "last_error": "parse failed",
        "last_error_type": "ValueError",
    }


def test_parser_worker_retries_dramatiq_time_limit_exceptions(
    tmp_path: Path,
) -> None:
    settings = Settings(storage_dir=tmp_path, parser_max_retry_attempts=1)
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
        document_parse_service=TimeLimitDocumentParseService(),
        job_repository=repository,
        dispatch_service=_build_dispatch_service(settings, repository),
    )

    try:
        result = worker.process_job("job-1")
    finally:
        worker.shutdown()

    job = repository.get("job-1")
    assert job is not None
    assert result.retry_requested is True
    assert job.status == IngestionStatus.RETRYING
    assert job.error == "Time limit exceeded"
    assert job.metadata["parser_retry"] == {
        "state": "retrying",
        "failure_count": 1,
        "max_retries": 1,
        "last_error": "Time limit exceeded",
        "last_error_type": "TimeLimitExceeded",
    }


def test_parser_worker_resubmits_retrying_submitted_job_after_release(
    tmp_path: Path,
) -> None:
    settings = Settings(storage_dir=tmp_path)
    repository = SqliteIngestionJobRepository(settings.jobs_db_path)
    worker = _build_worker(settings, repository)
    worker._parse_coordinator = RetryingParseCoordinator()
    worker._submitted.add("job-1")
    resubmitted: list[str] = []
    worker.submit_job = resubmitted.append  # type: ignore[method-assign]

    try:
        worker._run_submitted_job("job-1")
    finally:
        worker.shutdown()

    assert "job-1" not in worker._submitted
    assert resubmitted == ["job-1"]


def test_parser_worker_releases_submitted_job_when_coordinator_raises(
    tmp_path: Path,
) -> None:
    settings = Settings(storage_dir=tmp_path)
    repository = SqliteIngestionJobRepository(settings.jobs_db_path)
    worker = _build_worker(settings, repository)
    worker._submitted.add("job-1")
    worker._parse_coordinator = RaisingParseCoordinator()

    try:
        with pytest.raises(RuntimeError, match="unexpected coordinator failure"):
            worker.process_job("job-1")
    finally:
        worker.shutdown()

    assert "job-1" not in worker._submitted


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
        parsed_document_dispatch_service=dispatch_service,
    )

    service.process_queued_job("job-1")
    service.process_dispatch_queue()

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


class TimeLimitExceeded(BaseException):
    __module__ = "dramatiq.middleware.time_limit"


class TimeLimitDocumentParseService:
    def parse_file(self, **_kwargs):
        raise TimeLimitExceeded("Time limit exceeded")


class RecordingDocumentParseService:
    def __init__(self, tmp_path: Path) -> None:
        self._tmp_path = tmp_path
        self.calls: list[dict] = []

    def parse_file(self, **kwargs) -> DocumentParseResult:
        self.calls.append(kwargs)
        document_id = str(kwargs["document_id"])
        return DocumentParseResult(
            content=ParsedDocumentContent(
                document_id=document_id,
                markdown="# Example",
                html="<h1>Example</h1>" if kwargs.get("include_html") else None,
                metadata={
                    "input_format": "md",
                    "parser": "docling",
                    "pipeline": "standard",
                    "source_file_name": "example.md",
                },
                rag_records=[
                    RagIngestionRecord(
                        record_id="record-1",
                        document_id=document_id,
                        job_id=document_id,
                        content="# Example",
                        title="example.md",
                        source_file_name="example.md",
                        input_format="md",
                        parser="docling",
                        pipeline="standard",
                        record_type="document",
                    )
                ],
            ),
            outputs=None,
            diagnostics=ParseDiagnostics(
                parser="docling",
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                duration_ms=1,
                chunk_count=0,
                metadata={"pipeline": "standard"},
            ),
        )


class RaisingParseCoordinator:
    def process_job(self, *_args, **_kwargs) -> None:
        raise RuntimeError("unexpected coordinator failure")


class RetryingParseCoordinator:
    def process_job(self, *_args, **_kwargs):
        from ingest_orquestator_server.application.services.job_parse_coordinator import (
            ParseJobResult,
        )

        return ParseJobResult(retry_requested=True)


class NoopParsedDocumentDispatchSink:
    def submit_batch(
        self, items: list[ParsedDocumentDispatchItem]
    ) -> DispatchSinkResult:
        accepted_record_count = sum(len(item.content.rag_records) for item in items)
        return DispatchSinkResult(
            accepted_document_count=len(items),
            accepted_record_count=accepted_record_count,
            raw_response={"mode": "bulk", "successful": accepted_record_count},
        )


class ManualParsedDocumentDispatchService(ParsedDocumentDispatchService):
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
        chunking_service=build_parser_chunking_service(settings),
    )


def _build_dispatch_service(
    settings: Settings,
    repository: SqliteIngestionJobRepository,
) -> ParsedDocumentDispatchService:
    return ManualParsedDocumentDispatchService(
        settings=settings,
        queue_service=ParsedDocumentDispatchQueueService(
            max_bulk_size=settings.dispatch_max_bulk_size
        ),
        dispatcher=NoopParsedDocumentDispatchSink(),
        job_repository=repository,
        output_writer=LocalParseOutputWriter(),
    )


def _write_input(tmp_path: Path) -> Path:
    input_path = tmp_path / "example.md"
    input_path.write_text("# Example\n", encoding="utf-8")
    return input_path
