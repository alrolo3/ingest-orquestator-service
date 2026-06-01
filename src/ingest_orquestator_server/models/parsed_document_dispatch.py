from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ingest_orquestator_server.models.parse_diagnostics import ParseDiagnostics
from ingest_orquestator_server.models.parsed_document_content import ParsedDocumentContent


class ParsedDocumentDispatchItemStatus(StrEnum):
    QUEUED = "queued"
    DISPATCHING = "dispatching"
    COMPLETED = "completed"
    FAILED = "failed"


class ParsedDocumentDispatchItem(BaseModel):
    model_config = ConfigDict(json_encoders={Path: str})

    queue_id: str
    job_id: str
    document_id: str
    source_file_name: str | None = None
    content: ParsedDocumentContent
    diagnostics: ParseDiagnostics
    output_dir: Path | None = None
    record_count: int = 0
    status: ParsedDocumentDispatchItemStatus = ParsedDocumentDispatchItemStatus.QUEUED
    attempts: int = 0
    last_error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    enqueued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ParsedDocumentDispatchQueueSnapshot(BaseModel):
    max_bulk_size: int
    max_size: int
    max_payload_bytes: int | None = None
    queued_count: int
    in_flight_count: int
    completed_count: int
    failed_count: int
    queued_items: list[ParsedDocumentDispatchItem]
    in_flight_items: list[ParsedDocumentDispatchItem]
    completed_items: list[ParsedDocumentDispatchItem]
    failed_items: list[ParsedDocumentDispatchItem]


class DispatchSinkResult(BaseModel):
    accepted_document_count: int
    accepted_record_count: int = 0
    raw_response: dict[str, Any] = Field(default_factory=dict)


class ParsedDocumentDispatchRunResult(BaseModel):
    queue_status: ParsedDocumentDispatchQueueSnapshot
    submitted_document_count: int = 0
    submitted_record_count: int = 0
