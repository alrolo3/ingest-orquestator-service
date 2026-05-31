from pathlib import Path

from ingest_orquestator_server.application.services.embedding_dispatch_service import (
    EmbeddingDispatchService,
)
from ingest_orquestator_server.application.services.embedding_queue_service import (
    EmbeddingQueueService,
)
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.sqlite.sqlite_ingestion_job_repository import (
    SqliteIngestionJobRepository,
)
from ingest_orquestator_server.models.embedding_queue import (
    EmbeddingDispatchResult,
    EmbeddingQueueItem,
    EmbeddingTaskStatus,
)
from ingest_orquestator_server.models.ingestion_job import IngestionJob
from ingest_orquestator_server.models.ingestion_status import IngestionStatus
from ingest_orquestator_server.models.output_files import OutputFiles


class FakeEmbeddingDispatcher:
    def __init__(self) -> None:
        self.submitted_batches: list[list[EmbeddingQueueItem]] = []
        self.completed = False

    def submit_batch(self, items: list[EmbeddingQueueItem]) -> EmbeddingDispatchResult:
        self.submitted_batches.append(items)
        return EmbeddingDispatchResult(
            task_id="task-1",
            accepted_document_count=len(items),
            raw_response={"task": "task-1"},
        )

    def get_task_status(self, task_id: str) -> EmbeddingTaskStatus:
        return EmbeddingTaskStatus(
            task_id=task_id,
            completed=self.completed,
            raw_response={"completed": self.completed},
        )


def test_embedding_dispatch_service_updates_job_handoff_states(tmp_path: Path) -> None:
    settings = Settings(
        storage_dir=tmp_path,
        embedding_queue_enabled=True,
        embedding_queue_max_bulk_size=5,
    )
    repository = SqliteIngestionJobRepository(settings.jobs_db_path)
    job = _job(tmp_path, "job-1")
    repository.save(job)
    dispatcher = FakeEmbeddingDispatcher()
    service = EmbeddingDispatchService(
        settings=settings,
        queue_service=EmbeddingQueueService(max_bulk_size=5),
        dispatcher=dispatcher,
        job_repository=repository,
    )

    queued = service.enqueue_job(job)
    task_id = service.dispatch_next_batch()

    sent = repository.get("job-1")
    assert queued.status == IngestionStatus.EMBEDDING_QUEUED
    assert task_id == "task-1"
    assert sent is not None
    assert sent.status == IngestionStatus.SENT_TO_EMBEDDING_SYSTEM
    assert sent.metadata["embedding_handoff"]["task_id"] == "task-1"

    dispatcher.completed = True
    result = service.run_once()

    completed = repository.get("job-1")
    assert result.completed_task_ids == ["task-1"]
    assert completed is not None
    assert completed.status == IngestionStatus.EMBEDDING_COMPLETED


def _job(tmp_path: Path, job_id: str) -> IngestionJob:
    output_dir = tmp_path / "outputs" / job_id
    output_dir.mkdir(parents=True)
    embedding_input = output_dir / "embedding_input.jsonl"
    embedding_input.write_text(
        '{"record_id":"1","document_id":"doc","chunk_id":"c1","text":"one"}\n',
        encoding="utf-8",
    )
    return IngestionJob(
        job_id=job_id,
        status=IngestionStatus.COMPLETED,
        parser="docling",
        source_file_name="sample.pdf",
        document_id=job_id,
        outputs=OutputFiles(
            output_dir=output_dir,
            raw_docling_json=output_dir / "raw_docling.json",
            normalized_json=output_dir / "normalized.json",
            markdown=output_dir / "document.md",
            text=output_dir / "document.txt",
            embedding_input_jsonl=embedding_input,
            manifest_json=output_dir / "manifest.json",
        ),
        metadata={"input_format": "pdf", "pipeline": "standard"},
    )
