from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ingest_orquestator_server.application.services.file_ingestion_service import (
    FileIngestionService,
)
from ingest_orquestator_server.application.validation.upload_validator import UploadValidator
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.filesystem.local_upload_storage import (
    LocalUploadStorage,
)
from ingest_orquestator_server.infrastructure.queue import DramatiqJobQueuePublisher
from ingest_orquestator_server.infrastructure.sqlite.sqlite_ingestion_job_repository import (
    SqliteIngestionJobRepository,
)
from ingest_orquestator_server.models.ingestion_status import IngestionStatus
from ingest_orquestator_server.models.parse_diagnostics import ParseDiagnostics
from ingest_orquestator_server.models.parsed_document_content import ParsedDocumentContent
from ingest_orquestator_server.models.parsed_document_dispatch import (
    ParsedDocumentDispatchItem,
)
from ingest_orquestator_server.models.rag_ingestion import RagIngestionRecord


class FakeUpload:
    filename = "example.md"
    content_type = "text/markdown"

    def __init__(self, content: bytes) -> None:
        self._content = content
        self._consumed = False

    async def read(self, _size: int = -1) -> bytes:
        if self._consumed:
            return b""
        self._consumed = True
        return self._content

    async def seek(self, _offset: int) -> None:
        self._consumed = False


class FakeDocumentParseService:
    pass


class RecordingJobQueue:
    def __init__(self) -> None:
        self.parser_job_ids: list[str] = []

    def enqueue_parser_job(self, job_id: str) -> None:
        self.parser_job_ids.append(job_id)


class RecordingActor:
    def __init__(self) -> None:
        self.messages: list[tuple[Any, ...]] = []

    def send(self, *args: Any, **_kwargs: Any) -> None:
        self.messages.append(args)


def test_file_ingestion_service_publishes_parser_job(tmp_path: Path) -> None:
    settings = Settings(storage_dir=tmp_path, allowed_upload_extensions=[".md"])
    repository = SqliteIngestionJobRepository(settings.jobs_db_path)
    validator = UploadValidator(settings)
    queue = RecordingJobQueue()
    service = FileIngestionService(
        settings=settings,
        upload_storage=LocalUploadStorage(upload_validator=validator),
        document_parse_service=FakeDocumentParseService(),
        job_repository=repository,
        upload_validator=validator,
        parser_job_queue=queue,
    )

    response = asyncio.run(
        service.enqueue_upload(
            upload=FakeUpload(b"# Example"),
            parser_name="docling",
            pipeline="standard",
        )
    )

    assert response.status == IngestionStatus.PARSER_QUEUED
    assert queue.parser_job_ids == [response.job_id]
    stored_job = repository.get(response.job_id)
    assert stored_job is not None
    assert stored_job.status == IngestionStatus.PARSER_QUEUED


def test_dramatiq_job_queue_publisher_sends_actor_messages() -> None:
    parser_actor = RecordingActor()
    dispatch_actor = RecordingActor()
    publisher = DramatiqJobQueuePublisher(
        parser_actor=parser_actor,
        dispatch_actor=dispatch_actor,
    )

    publisher.enqueue_parser_job("job-1")
    publisher.enqueue_dispatch_job(_dispatch_item())

    assert parser_actor.messages == [("job-1",)]
    assert dispatch_actor.messages[0][0]["queue_id"] == "queue-1"
    assert dispatch_actor.messages[0][0]["job_id"] == "job-1"


def _dispatch_item() -> ParsedDocumentDispatchItem:
    return ParsedDocumentDispatchItem(
        queue_id="queue-1",
        job_id="job-1",
        document_id="document-1",
        source_file_name="example.md",
        content=ParsedDocumentContent(
            document_id="document-1",
            markdown="# Example",
            metadata={
                "input_format": "md",
                "parser": "docling",
                "pipeline": "standard",
                "source_file_name": "example.md",
            },
            rag_records=[
                RagIngestionRecord(
                    record_id="record-1",
                    document_id="document-1",
                    job_id="job-1",
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
        diagnostics=ParseDiagnostics(
            parser="docling",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            duration_ms=1,
            chunk_count=0,
            metadata={},
        ),
    )
