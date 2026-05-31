from pathlib import Path

from ingest_orquestator_server.application.services.embedding_queue_service import (
    EmbeddingQueueService,
)
from ingest_orquestator_server.models.ingestion_job import IngestionJob
from ingest_orquestator_server.models.ingestion_status import IngestionStatus
from ingest_orquestator_server.models.output_files import OutputFiles


def test_embedding_queue_enqueues_completed_job_once(tmp_path: Path) -> None:
    job = _job(tmp_path, "job-1")
    service = EmbeddingQueueService(max_bulk_size=5)

    first = service.enqueue_job(job)
    second = service.enqueue_job(job)

    assert first.queue_id == second.queue_id
    assert service.snapshot().queued_count == 1
    assert first.record_count == 2


def test_embedding_queue_dequeues_at_configured_bulk_limit(tmp_path: Path) -> None:
    service = EmbeddingQueueService(max_bulk_size=2)
    for index in range(3):
        service.enqueue_job(_job(tmp_path, f"job-{index}"))

    batch = service.dequeue_batch()

    assert len(batch) == 2
    assert service.snapshot().queued_count == 1
    assert service.snapshot().in_flight_count == 2


def _job(tmp_path: Path, job_id: str) -> IngestionJob:
    output_dir = tmp_path / job_id
    output_dir.mkdir()
    embedding_input = output_dir / "embedding_input.jsonl"
    embedding_input.write_text(
        '{"record_id":"1","document_id":"doc","chunk_id":"c1","text":"one"}\n'
        '{"record_id":"2","document_id":"doc","chunk_id":"c2","text":"two"}\n',
        encoding="utf-8",
    )
    outputs = OutputFiles(
        output_dir=output_dir,
        raw_docling_json=output_dir / "raw_docling.json",
        normalized_json=output_dir / "normalized.json",
        markdown=output_dir / "document.md",
        text=output_dir / "document.txt",
        embedding_input_jsonl=embedding_input,
        manifest_json=output_dir / "manifest.json",
    )
    return IngestionJob(
        job_id=job_id,
        status=IngestionStatus.COMPLETED,
        parser="docling",
        source_file_name=f"{job_id}.pdf",
        document_id=job_id,
        outputs=outputs,
        metadata={"input_format": "pdf", "pipeline": "standard"},
    )
