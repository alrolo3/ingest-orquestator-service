from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from ingest_orquestator_server.models.ingestion_status import IngestionStatus


class QueueJobSummary(BaseModel):
    job_id: str
    status: IngestionStatus
    parser: str
    source_file_name: str | None = None
    document_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class QueueStageMetrics(BaseModel):
    name: str
    statuses: list[IngestionStatus]
    count: int
    jobs: list[QueueJobSummary] = Field(default_factory=list)


class DispatchQueueCounts(BaseModel):
    max_bulk_size: int
    max_size: int
    max_payload_bytes: int | None = None
    queued_count: int
    in_flight_count: int
    completed_count: int
    failed_count: int


class QueueMetrics(BaseModel):
    queue_backend: str
    parser_queue_name: str
    dispatch_queue_name: str
    parser_worker_count: int
    dispatch_worker_count: int
    status_counts: dict[str, int]
    stages: list[QueueStageMetrics]
    dispatch_queue: DispatchQueueCounts | None = None
