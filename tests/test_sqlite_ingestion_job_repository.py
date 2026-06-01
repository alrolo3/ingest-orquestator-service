from pathlib import Path

from ingest_orquestator_server.infrastructure.sqlite.sqlite_ingestion_job_repository import (
    SqliteIngestionJobRepository,
)
from ingest_orquestator_server.models.ingestion_job import IngestionJob
from ingest_orquestator_server.models.ingestion_status import IngestionStatus
from ingest_orquestator_server.models.output_files import OutputFiles


def test_sqlite_repository_saves_and_loads_jobs(tmp_path: Path) -> None:
    repository = SqliteIngestionJobRepository(tmp_path / "jobs.sqlite3")
    job = IngestionJob(
        job_id="job-1",
        status=IngestionStatus.COMPLETED,
        parser="docling",
        source_file_name="example.pdf",
        input_path=tmp_path / "uploads" / "example.pdf",
        document_id="job-1",
        metadata={"pipeline": "standard", "input_format": "pdf"},
        outputs=OutputFiles(
            output_dir=tmp_path / "outputs" / "job-1",
            markdown=tmp_path / "outputs" / "job-1" / "document.md",
            document_metadata_json=tmp_path
            / "outputs"
            / "job-1"
            / "document_metadata.json",
            rag_chunks_jsonl=tmp_path / "outputs" / "job-1" / "rag_chunks.jsonl",
        ),
    )

    repository.save(job)
    loaded = repository.get("job-1")

    assert loaded is not None
    assert loaded.status == IngestionStatus.COMPLETED
    assert loaded.metadata["pipeline"] == "standard"
    assert loaded.outputs is not None
    assert loaded.outputs.rag_chunks_jsonl is not None


def test_sqlite_repository_lists_active_jobs(tmp_path: Path) -> None:
    repository = SqliteIngestionJobRepository(tmp_path / "jobs.sqlite3")
    repository.save(
        IngestionJob(job_id="running", status=IngestionStatus.RUNNING, parser="docling")
    )
    repository.save(IngestionJob(job_id="queued", status=IngestionStatus.QUEUED, parser="docling"))
    repository.save(IngestionJob(job_id="done", status=IngestionStatus.COMPLETED, parser="docling"))

    assert repository.list_active_job_ids() == {"queued", "running"}


def test_sqlite_repository_deletes_job(tmp_path: Path) -> None:
    repository = SqliteIngestionJobRepository(tmp_path / "jobs.sqlite3")
    repository.save(
        IngestionJob(
            job_id="job-1",
            status=IngestionStatus.PARSER_QUEUED,
            parser="docling",
        )
    )

    deleted = repository.delete("job-1")

    assert deleted is not None
    assert deleted.job_id == "job-1"
    assert repository.get("job-1") is None
    assert repository.delete("missing") is None
