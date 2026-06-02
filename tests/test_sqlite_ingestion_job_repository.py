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


def test_sqlite_repository_groups_runs_by_content_hash(tmp_path: Path) -> None:
    repository = SqliteIngestionJobRepository(tmp_path / "jobs.sqlite3")
    document = repository.upsert_document(
        content_hash="abc123",
        source_file_name="example.md",
        size_bytes=10,
        mime_type="text/markdown",
        storage_path=tmp_path / "uploads" / "example.md",
    )
    same_document = repository.upsert_document(
        content_hash="abc123",
        source_file_name="example-renamed.md",
        size_bytes=10,
        mime_type="text/markdown",
        storage_path=tmp_path / "uploads" / "example-renamed.md",
    )

    assert same_document.document_id == document.document_id

    first_job = IngestionJob(
        job_id="run-1",
        status=IngestionStatus.COMPLETED,
        parser="docling",
        source_file_name="example.md",
        input_path=tmp_path / "uploads" / "example.md",
        document_id=document.document_id,
        metadata={"requested_pipeline": "standard"},
    )
    second_job = IngestionJob(
        job_id="run-2",
        status=IngestionStatus.FAILED,
        parser="docling",
        source_file_name="example.md",
        input_path=tmp_path / "uploads" / "example.md",
        document_id=document.document_id,
        metadata={"requested_pipeline": "vlm"},
        error="VLM failed",
    )
    repository.save(first_job)
    repository.create_run_for_job(first_job, document_id=document.document_id)
    repository.save(second_job)
    repository.create_run_for_job(second_job, document_id=document.document_id)

    page = repository.list_documents(limit=10)

    assert page.total == 1
    assert page.next_cursor is None
    assert page.documents[0].document.document_id == document.document_id
    assert [run.run_id for run in page.documents[0].runs] == ["run-2", "run-1"]
    assert page.documents[0].latest_run is not None
    assert page.documents[0].latest_run.status == IngestionStatus.FAILED
    assert [run.run_id for run in repository.list_runs(["run-1", "missing", "run-2"])] == [
        "run-1",
        "run-2",
    ]


def test_sqlite_repository_paginates_documents(tmp_path: Path) -> None:
    repository = SqliteIngestionJobRepository(tmp_path / "jobs.sqlite3")
    for index in range(3):
        repository.upsert_document(
            content_hash=f"hash-{index}",
            source_file_name=f"example-{index}.md",
            size_bytes=index,
            mime_type="text/markdown",
            storage_path=tmp_path / f"example-{index}.md",
        )

    first_page = repository.list_documents(limit=2)
    second_page = repository.list_documents(limit=2, cursor=first_page.next_cursor)

    assert len(first_page.documents) == 2
    assert first_page.next_cursor == "2"
    assert len(second_page.documents) == 1
    assert second_page.next_cursor is None
