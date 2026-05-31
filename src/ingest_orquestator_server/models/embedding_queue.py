from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ingest_orquestator_server.models.document_chunk import DocumentChunk
from ingest_orquestator_server.models.embedding_record import EmbeddingRecord
from ingest_orquestator_server.models.parse_diagnostics import ParseDiagnostics
from ingest_orquestator_server.models.parse_output import ParseOutput


class EmbeddingQueueItemStatus(StrEnum):
    QUEUED = "queued"
    DISPATCHING = "dispatching"
    COMPLETED = "completed"
    FAILED = "failed"


class EmbeddingQueueItem(BaseModel):
    model_config = ConfigDict(json_encoders={Path: str})

    queue_id: str
    job_id: str
    document_id: str
    source_file_name: str | None = None
    parse_output: ParseOutput
    chunks: list[DocumentChunk] = Field(default_factory=list)
    embedding_records: list[EmbeddingRecord] = Field(default_factory=list)
    diagnostics: ParseDiagnostics
    output_dir: Path | None = None
    record_count: int = 0
    status: EmbeddingQueueItemStatus = EmbeddingQueueItemStatus.QUEUED
    attempts: int = 0
    last_error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    enqueued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EmbeddingQueueSnapshot(BaseModel):
    max_bulk_size: int
    max_size: int
    max_payload_bytes: int | None = None
    queued_count: int
    in_flight_count: int
    completed_count: int
    failed_count: int
    queued_items: list[EmbeddingQueueItem]
    in_flight_items: list[EmbeddingQueueItem]
    completed_items: list[EmbeddingQueueItem]
    failed_items: list[EmbeddingQueueItem]


class EmbeddingDispatchResult(BaseModel):
    accepted_document_count: int
    accepted_chunk_count: int = 0
    raw_response: dict[str, Any] = Field(default_factory=dict)


class EmbeddingDispatchRunResult(BaseModel):
    queue_status: EmbeddingQueueSnapshot
    submitted_document_count: int = 0
    submitted_chunk_count: int = 0


DispatchQueueItem = EmbeddingQueueItem
DispatchQueueItemStatus = EmbeddingQueueItemStatus
DispatchQueueSnapshot = EmbeddingQueueSnapshot
DispatchResult = EmbeddingDispatchResult
DispatchRunResult = EmbeddingDispatchRunResult
