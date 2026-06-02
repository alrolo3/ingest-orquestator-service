from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from ingest_orquestator_server.models.ingest_response import IngestResponse
from ingest_orquestator_server.models.ingestion_status import IngestionStatus
from ingest_orquestator_server.models.output_files import OutputFiles


class IngestionDocument(BaseModel):
    document_id: str
    content_hash: str
    source_file_name: str | None = None
    size_bytes: int | None = None
    mime_type: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class IngestionRunSummary(BaseModel):
    run_id: str
    job_id: str
    document_id: str
    attempt_number: int
    status: IngestionStatus
    parser: str
    pipeline: str | None = None
    source_file_name: str | None = None
    status_url: str
    outputs_url: str
    outputs: OutputFiles | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None


class IngestionDocumentEnvelope(BaseModel):
    document: IngestionDocument
    latest_run: IngestionRunSummary | None = None
    runs: list[IngestionRunSummary] = Field(default_factory=list)


class IngestionDocumentListResponse(BaseModel):
    documents: list[IngestionDocumentEnvelope]
    next_cursor: str | None = None
    total: int


class IngestDocumentsResponse(BaseModel):
    documents: list[IngestionDocumentEnvelope] = Field(default_factory=list)
    failed: list[IngestResponse] = Field(default_factory=list)


class IngestionRunListResponse(BaseModel):
    runs: list[IngestionRunSummary]
