from datetime import UTC, datetime
from pathlib import Path

from ingest_orquestator_server.application.services.document_parse_service import (
    DocumentParseResult,
)
from ingest_orquestator_server.application.services.parsed_document_dispatch_queue_service import (
    ParsedDocumentDispatchQueueService,
)
from ingest_orquestator_server.application.services.parsed_document_dispatch_service import (
    ParsedDocumentDispatchService,
)
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.filesystem.local_parse_output_writer import (
    LocalParseOutputWriter,
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


class FakeParsedDocumentDispatchSink:
    def __init__(self) -> None:
        self.submitted_batches: list[list[ParsedDocumentDispatchItem]] = []
        self.completed = False

    def submit_batch(
        self, items: list[ParsedDocumentDispatchItem]
    ) -> DispatchSinkResult:
        self.submitted_batches.append(items)
        accepted_record_count = sum(len(item.content.rag_records) for item in items)
        return DispatchSinkResult(
            accepted_document_count=len(items),
            accepted_record_count=accepted_record_count,
            raw_response={"mode": "bulk", "successful": accepted_record_count},
        )


class RecordingDispatchQueue:
    def __init__(self) -> None:
        self.queue_ids: list[str] = []

    def enqueue_dispatch_job(self, item: ParsedDocumentDispatchItem) -> None:
        self.queue_ids.append(item.queue_id)


class RepositoryInspectingDispatchQueue:
    def __init__(self, repository: SqliteIngestionJobRepository) -> None:
        self._repository = repository
        self.statuses_at_publish: list[IngestionStatus] = []

    def enqueue_dispatch_job(self, item: ParsedDocumentDispatchItem) -> None:
        job = self._repository.get(item.job_id)
        assert job is not None
        self.statuses_at_publish.append(job.status)


def test_parsed_document_dispatch_service_updates_job_handoff_states(
    tmp_path: Path,
) -> None:
    settings = Settings(
        storage_dir=tmp_path,
        dispatch_sink_mode="local_and_elastic",
        dispatch_max_bulk_size=5,
    )
    repository = SqliteIngestionJobRepository(settings.jobs_db_path)
    job = _job("job-1")
    repository.save(job)
    dispatcher = FakeParsedDocumentDispatchSink()
    service = ParsedDocumentDispatchService(
        settings=settings,
        queue_service=ParsedDocumentDispatchQueueService(max_bulk_size=5),
        dispatcher=dispatcher,
        job_repository=repository,
        output_writer=LocalParseOutputWriter(),
    )

    queued = service.enqueue_parse_result(job, _parse_result("job-1"))
    accepted_document_count = service.dispatch_next_batch()

    completed = repository.get("job-1")
    assert queued.status == IngestionStatus.DISPATCH_QUEUED
    assert accepted_document_count == 1
    assert completed is not None
    assert completed.status == IngestionStatus.COMPLETED
    assert completed.outputs is not None
    assert completed.outputs.document_metadata_json is not None
    assert completed.outputs.rag_chunks_jsonl is not None
    assert (
        completed.metadata["dispatch_handoff"]["last_response"]["elastic_response"]["mode"]
        == "bulk"
    )

    result = service.run_once()

    assert result.submitted_document_count == 0


def test_parsed_document_dispatch_service_publishes_dispatch_queue_item(
    tmp_path: Path,
) -> None:
    settings = Settings(storage_dir=tmp_path)
    repository = SqliteIngestionJobRepository(settings.jobs_db_path)
    job = _job("job-1")
    repository.save(job)
    dispatch_queue = RecordingDispatchQueue()
    service = ParsedDocumentDispatchService(
        settings=settings,
        queue_service=ParsedDocumentDispatchQueueService(max_bulk_size=5),
        dispatcher=FakeParsedDocumentDispatchSink(),
        job_repository=repository,
        output_writer=LocalParseOutputWriter(),
        dispatch_job_queue=dispatch_queue,
    )

    queued = service.enqueue_parse_result(job, _parse_result("job-1"))

    assert queued.status == IngestionStatus.DISPATCH_QUEUED
    assert dispatch_queue.queue_ids == queued.metadata["dispatch_handoff"]["queue_ids"]


def test_parsed_document_dispatch_service_saves_job_before_publishing_dispatch(
    tmp_path: Path,
) -> None:
    settings = Settings(storage_dir=tmp_path)
    repository = SqliteIngestionJobRepository(settings.jobs_db_path)
    job = _job("job-1")
    repository.save(job)
    dispatch_queue = RepositoryInspectingDispatchQueue(repository)
    service = ParsedDocumentDispatchService(
        settings=settings,
        queue_service=ParsedDocumentDispatchQueueService(max_bulk_size=5),
        dispatcher=FakeParsedDocumentDispatchSink(),
        job_repository=repository,
        output_writer=LocalParseOutputWriter(),
        dispatch_job_queue=dispatch_queue,
    )

    service.enqueue_parse_result(job, _parse_result("job-1"))

    assert dispatch_queue.statuses_at_publish == [IngestionStatus.DISPATCH_QUEUED]


def test_parsed_document_dispatch_service_uses_job_dispatch_sink_mode(
    tmp_path: Path,
) -> None:
    settings = Settings(storage_dir=tmp_path, dispatch_sink_mode="local")
    repository = SqliteIngestionJobRepository(settings.jobs_db_path)
    job = _job("job-1").model_copy(
        update={"metadata": {"requested_dispatch_sink_mode": "elastic"}}
    )
    repository.save(job)
    dispatcher = FakeParsedDocumentDispatchSink()
    service = ParsedDocumentDispatchService(
        settings=settings,
        queue_service=ParsedDocumentDispatchQueueService(max_bulk_size=5),
        dispatcher=dispatcher,
        job_repository=repository,
        output_writer=LocalParseOutputWriter(),
    )

    service.enqueue_parse_result(job, _parse_result("job-1"))
    accepted_document_count = service.dispatch_next_batch()

    completed = repository.get("job-1")
    assert accepted_document_count == 1
    assert len(dispatcher.submitted_batches) == 1
    assert completed is not None
    assert completed.status == IngestionStatus.COMPLETED
    assert completed.outputs is None
    assert completed.metadata["dispatch_handoff"]["sink_mode"] == "elastic"


def test_parsed_document_dispatch_service_skips_deleted_jobs(
    tmp_path: Path,
) -> None:
    settings = Settings(storage_dir=tmp_path)
    repository = SqliteIngestionJobRepository(settings.jobs_db_path)
    job = _job("job-1")
    repository.save(job)
    queue_service = ParsedDocumentDispatchQueueService(max_bulk_size=5)
    dispatcher = FakeParsedDocumentDispatchSink()
    service = ParsedDocumentDispatchService(
        settings=settings,
        queue_service=queue_service,
        dispatcher=dispatcher,
        job_repository=repository,
        output_writer=LocalParseOutputWriter(),
    )
    service.enqueue_parse_result(job, _parse_result("job-1"))
    repository.delete("job-1")

    accepted_document_count = service.dispatch_next_batch()

    assert accepted_document_count == 0
    assert dispatcher.submitted_batches == []
    assert queue_service.snapshot().completed_count == 1


def test_parsed_document_dispatch_service_starts_configured_worker_pool(
    tmp_path: Path,
) -> None:
    settings = Settings(storage_dir=tmp_path, dispatch_worker_count=3)
    repository = SqliteIngestionJobRepository(settings.jobs_db_path)
    service = ParsedDocumentDispatchService(
        settings=settings,
        queue_service=ParsedDocumentDispatchQueueService(max_bulk_size=5),
        dispatcher=FakeParsedDocumentDispatchSink(),
        job_repository=repository,
        output_writer=LocalParseOutputWriter(),
    )

    service.start()
    try:
        assert len(service._threads) == 3
        assert all(thread.is_alive() for thread in service._threads)
    finally:
        service.stop()

    assert service._threads == []


def _job(job_id: str) -> IngestionJob:
    return IngestionJob(
        job_id=job_id,
        status=IngestionStatus.PARSED,
        parser="docling",
        source_file_name="sample.pdf",
        document_id=job_id,
        metadata={"input_format": "pdf", "pipeline": "standard"},
    )


def _parse_result(document_id: str) -> DocumentParseResult:
    diagnostics = ParseDiagnostics(
        parser="docling",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        duration_ms=1,
        chunk_count=1,
        metadata={"input_format": "pdf", "pipeline": "standard"},
    )
    return DocumentParseResult(
        content=ParsedDocumentContent(
            document_id=document_id,
            markdown="one",
            metadata={
                "input_format": "pdf",
                "parser": "docling",
                "pipeline": "standard",
                "source_file_name": "sample.pdf",
            },
            rag_records=[
                RagIngestionRecord(
                    record_id="1",
                    document_id=document_id,
                    job_id=document_id,
                    content="one",
                    title="Sample",
                    source_file_name="sample.pdf",
                    input_format="pdf",
                    parser="docling",
                    pipeline="standard",
                    chunk_id="c1",
                    metadata={"title": "Sample"},
                )
            ],
        ),
        outputs=None,
        diagnostics=diagnostics,
    )
