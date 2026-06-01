from pathlib import Path

from ingest_orquestator_server.application.services.job_removal_service import (
    JobRemovalService,
)
from ingest_orquestator_server.application.services.parsed_document_dispatch_queue_service import (
    ParsedDocumentDispatchQueueService,
)
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.sqlite.sqlite_ingestion_job_repository import (
    SqliteIngestionJobRepository,
)
from ingest_orquestator_server.models.ingestion_job import IngestionJob
from ingest_orquestator_server.models.ingestion_status import IngestionStatus
from ingest_orquestator_server.models.output_files import OutputFiles


def test_job_removal_deletes_queued_job(tmp_path: Path) -> None:
    settings = Settings(storage_dir=tmp_path)
    repository = SqliteIngestionJobRepository(settings.jobs_db_path)
    upload_path = settings.uploads_dir / "job-1-example.pdf"
    upload_path.parent.mkdir(parents=True, exist_ok=True)
    upload_path.write_text("pdf")
    repository.save(
        IngestionJob(
            job_id="job-1",
            status=IngestionStatus.PARSER_QUEUED,
            parser="docling",
            input_path=upload_path,
        )
    )
    service = JobRemovalService(settings=settings, job_repository=repository)

    result = service.remove_job("job-1")

    assert result is not None
    assert result.job_id == "job-1"
    assert result.previous_status == IngestionStatus.PARSER_QUEUED
    assert result.parser_process_terminated is False
    assert result.removed_artifact_count == 1
    assert repository.get("job-1") is None
    assert not upload_path.exists()


def test_job_removal_terminates_recorded_parser_process(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = Settings(storage_dir=tmp_path)
    repository = SqliteIngestionJobRepository(settings.jobs_db_path)
    killed: list[tuple[int, int]] = []
    monkeypatch.setattr(
        "ingest_orquestator_server.application.services.job_removal_service.os.kill",
        lambda pid, sig: killed.append((pid, sig)),
    )
    repository.save(
        IngestionJob(
            job_id="job-1",
            status=IngestionStatus.PARSING,
            parser="docling",
            metadata={"parser_runtime": {"pid": 4242}},
        )
    )
    service = JobRemovalService(settings=settings, job_repository=repository)

    result = service.remove_job("job-1")

    assert result is not None
    assert result.previous_status == IngestionStatus.PARSING
    assert result.parser_process_terminated is True
    assert killed == [(4242, 15)]
    assert repository.get("job-1") is None


def test_job_removal_deletes_completed_job_outputs(tmp_path: Path) -> None:
    settings = Settings(storage_dir=tmp_path)
    repository = SqliteIngestionJobRepository(settings.jobs_db_path)
    output_dir = settings.outputs_dir / "job-1"
    output_dir.mkdir(parents=True)
    markdown = output_dir / "document.md"
    metadata = output_dir / "document_metadata.json"
    markdown.write_text("# document")
    metadata.write_text("{}")
    repository.save(
        IngestionJob(
            job_id="job-1",
            status=IngestionStatus.COMPLETED,
            parser="docling",
            outputs=OutputFiles(
                output_dir=output_dir,
                markdown=markdown,
                document_metadata_json=metadata,
            ),
        )
    )
    service = JobRemovalService(settings=settings, job_repository=repository)

    result = service.remove_job("job-1")

    assert result is not None
    assert result.previous_status == IngestionStatus.COMPLETED
    assert result.removed_artifact_count == 1
    assert repository.get("job-1") is None
    assert not output_dir.exists()


def test_job_removal_does_not_delete_storage_roots_from_job_metadata(
    tmp_path: Path,
) -> None:
    settings = Settings(storage_dir=tmp_path)
    repository = SqliteIngestionJobRepository(settings.jobs_db_path)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    repository.save(
        IngestionJob(
            job_id="job-1",
            status=IngestionStatus.COMPLETED,
            parser="docling",
            input_path=settings.uploads_dir,
        )
    )
    service = JobRemovalService(settings=settings, job_repository=repository)

    result = service.remove_job("job-1")

    assert result is not None
    assert result.removed_artifact_count == 0
    assert settings.uploads_dir.exists()


def test_job_removal_removes_local_dispatch_queue_item(tmp_path: Path) -> None:
    settings = Settings(storage_dir=tmp_path)
    repository = SqliteIngestionJobRepository(settings.jobs_db_path)
    queue_service = ParsedDocumentDispatchQueueService(max_bulk_size=5)
    repository.save(
        IngestionJob(
            job_id="job-1",
            status=IngestionStatus.DISPATCH_QUEUED,
            parser="docling",
        )
    )
    queue_service._job_index["job-1"] = "queue-1"
    service = JobRemovalService(
        settings=settings,
        job_repository=repository,
        dispatch_queue_service=queue_service,
    )

    result = service.remove_job("job-1")

    assert result is not None
    assert result.removed_dispatch_queue_item is True
    assert repository.get("job-1") is None
