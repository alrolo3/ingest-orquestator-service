from datetime import UTC, datetime
from pathlib import Path

from ingest_orquestator_server.application.services.document_parse_service import (
    DocumentParseResult,
)
from ingest_orquestator_server.application.services.embedding_queue_service import (
    EmbeddingQueueError,
    EmbeddingQueueService,
)
from ingest_orquestator_server.models.embedding_record import EmbeddingRecord
from ingest_orquestator_server.models.ingestion_job import IngestionJob
from ingest_orquestator_server.models.ingestion_status import IngestionStatus
from ingest_orquestator_server.models.parse_diagnostics import ParseDiagnostics
from ingest_orquestator_server.models.parse_output import ParseOutput
from ingest_orquestator_server.models.parsed_document import ParsedDocument


def test_embedding_queue_enqueues_completed_job_once(tmp_path: Path) -> None:
    job = _job(tmp_path, "job-1")
    service = EmbeddingQueueService(max_bulk_size=5)

    parse_result = _parse_result(tmp_path, "job-1")
    first = service.enqueue_parse_result(job, parse_result)
    second = service.enqueue_parse_result(job, parse_result)

    assert first.queue_id == second.queue_id
    assert service.snapshot().queued_count == 1
    assert first.record_count == 2


def test_embedding_queue_dequeues_at_configured_bulk_limit(tmp_path: Path) -> None:
    service = EmbeddingQueueService(max_bulk_size=2)
    for index in range(3):
        job_id = f"job-{index}"
        service.enqueue_parse_result(_job(tmp_path, job_id), _parse_result(tmp_path, job_id))

    batch = service.dequeue_batch()

    assert len(batch) == 2
    assert service.snapshot().queued_count == 1
    assert service.snapshot().in_flight_count == 2
    assert service.snapshot().max_payload_bytes is None


def test_embedding_queue_rejects_oversized_payload(tmp_path: Path) -> None:
    service = EmbeddingQueueService(max_bulk_size=2, max_payload_bytes=10)

    try:
        service.enqueue_parse_result(_job(tmp_path, "job-1"), _parse_result(tmp_path, "job-1"))
    except EmbeddingQueueError as exc:
        assert "payload is too large" in str(exc)
    else:
        raise AssertionError("Expected oversized dispatch queue payload to fail")


def _job(tmp_path: Path, job_id: str) -> IngestionJob:
    return IngestionJob(
        job_id=job_id,
        status=IngestionStatus.PARSED,
        parser="docling",
        source_file_name=f"{job_id}.pdf",
        document_id=job_id,
        metadata={"input_format": "pdf", "pipeline": "standard"},
    )


def _parse_result(tmp_path: Path, document_id: str) -> DocumentParseResult:
    parse_output = ParseOutput(
        document=ParsedDocument(
            document_id=document_id,
            source_file_name=f"{document_id}.pdf",
            source_path=str(tmp_path / f"{document_id}.pdf"),
        ),
        raw_docling={},
        raw_markdown="one\ntwo",
        raw_text="one\ntwo",
    )
    diagnostics = ParseDiagnostics(
        parser="docling",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        duration_ms=1,
        chunk_count=2,
        metadata={"input_format": "pdf", "pipeline": "standard"},
    )
    return DocumentParseResult(
        parse_output=parse_output,
        outputs=None,
        chunks=[],
        embedding_records=[
            EmbeddingRecord(record_id="1", document_id=document_id, chunk_id="c1", text="one"),
            EmbeddingRecord(record_id="2", document_id=document_id, chunk_id="c2", text="two"),
        ],
        diagnostics=diagnostics,
    )
