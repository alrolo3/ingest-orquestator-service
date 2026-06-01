from datetime import UTC, datetime
from pathlib import Path

from ingest_orquestator_server.application.services.document_parse_service import (
    DocumentParseResult,
)
from ingest_orquestator_server.application.services.parsed_document_dispatch_queue_service import (
    ParsedDocumentDispatchQueueError,
    ParsedDocumentDispatchQueueService,
)
from ingest_orquestator_server.models.ingestion_job import IngestionJob
from ingest_orquestator_server.models.ingestion_status import IngestionStatus
from ingest_orquestator_server.models.parse_diagnostics import ParseDiagnostics
from ingest_orquestator_server.models.parsed_document_content import ParsedDocumentContent
from ingest_orquestator_server.models.rag_ingestion import RagIngestionRecord


def test_parsed_document_dispatch_queue_enqueues_completed_job_once(
    tmp_path: Path,
) -> None:
    job = _job(tmp_path, "job-1")
    service = ParsedDocumentDispatchQueueService(max_bulk_size=5)

    parse_result = _parse_result("job-1")
    first = service.enqueue_parse_result(job, parse_result)
    second = service.enqueue_parse_result(job, parse_result)

    assert first.queue_id == second.queue_id
    assert service.snapshot().queued_count == 1
    assert first.record_count == 2


def test_parsed_document_dispatch_queue_dequeues_at_configured_bulk_limit(
    tmp_path: Path,
) -> None:
    service = ParsedDocumentDispatchQueueService(max_bulk_size=2)
    for index in range(3):
        job_id = f"job-{index}"
        service.enqueue_parse_result(_job(tmp_path, job_id), _parse_result(job_id))

    batch = service.dequeue_batch()

    assert len(batch) == 2
    assert service.snapshot().queued_count == 1
    assert service.snapshot().in_flight_count == 2
    assert service.snapshot().max_payload_bytes is None


def test_parsed_document_dispatch_queue_rejects_oversized_payload(
    tmp_path: Path,
) -> None:
    service = ParsedDocumentDispatchQueueService(max_bulk_size=2, max_payload_bytes=10)

    try:
        service.enqueue_parse_result(_job(tmp_path, "job-1"), _parse_result("job-1"))
    except ParsedDocumentDispatchQueueError as exc:
        assert "payload is too large" in str(exc)
    else:
        raise AssertionError("Expected oversized dispatch queue payload to fail")


def test_parsed_document_dispatch_payload_excludes_raw_parser_objects(
    tmp_path: Path,
) -> None:
    service = ParsedDocumentDispatchQueueService(max_bulk_size=2)

    item = service.enqueue_parse_result(_job(tmp_path, "job-1"), _parse_result("job-1"))
    payload = item.model_dump(mode="json")

    assert "content" in payload
    assert "parse_output" not in payload
    assert "raw_docling" not in str(payload)
    assert "chunking_document" not in str(payload)


def test_parsed_document_dispatch_queue_removes_item_by_job_id(
    tmp_path: Path,
) -> None:
    service = ParsedDocumentDispatchQueueService(max_bulk_size=2)
    service.enqueue_parse_result(_job(tmp_path, "job-1"), _parse_result("job-1"))

    removed = service.remove_by_job_id("job-1")

    assert removed is True
    assert service.snapshot().queued_count == 0
    assert service.dequeue_batch() == []
    assert service.remove_by_job_id("missing") is False


def _job(tmp_path: Path, job_id: str) -> IngestionJob:
    return IngestionJob(
        job_id=job_id,
        status=IngestionStatus.PARSED,
        parser="docling",
        source_file_name=f"{job_id}.pdf",
        document_id=job_id,
        metadata={"input_format": "pdf", "pipeline": "standard"},
    )


def _parse_result(document_id: str) -> DocumentParseResult:
    diagnostics = ParseDiagnostics(
        parser="docling",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        duration_ms=1,
        chunk_count=2,
        metadata={"input_format": "pdf", "pipeline": "standard"},
    )
    return DocumentParseResult(
        content=ParsedDocumentContent(
            document_id=document_id,
            markdown="one\ntwo",
            metadata={
                "job_id": document_id,
                "input_format": "pdf",
                "pipeline": "standard",
            },
            rag_records=[
                RagIngestionRecord(
                    record_id="1",
                    document_id=document_id,
                    job_id=document_id,
                    content="one",
                ),
                RagIngestionRecord(
                    record_id="2",
                    document_id=document_id,
                    job_id=document_id,
                    content="two",
                ),
            ],
        ),
        outputs=None,
        diagnostics=diagnostics,
    )
