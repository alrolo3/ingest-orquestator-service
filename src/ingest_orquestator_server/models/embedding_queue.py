from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EmbeddingQueueItemStatus(StrEnum):
    QUEUED = "queued"
    DISPATCHING = "dispatching"
    SENT = "sent"
    COMPLETED = "completed"
    FAILED = "failed"


class EmbeddingQueueItem(BaseModel):
    model_config = ConfigDict(json_encoders={Path: str})

    queue_id: str
    job_id: str
    document_id: str
    source_file_name: str | None = None
    embedding_input_path: Path
    output_dir: Path | None = None
    record_count: int
    status: EmbeddingQueueItemStatus = EmbeddingQueueItemStatus.QUEUED
    attempts: int = 0
    task_id: str | None = None
    last_error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    enqueued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EmbeddingQueueSnapshot(BaseModel):
    max_bulk_size: int
    queued_count: int
    in_flight_count: int
    completed_count: int
    failed_count: int
    active_task_ids: list[str]
    queued_items: list[EmbeddingQueueItem]
    in_flight_items: list[EmbeddingQueueItem]
    completed_items: list[EmbeddingQueueItem]
    failed_items: list[EmbeddingQueueItem]


class EmbeddingDispatchResult(BaseModel):
    task_id: str
    accepted_document_count: int
    raw_response: dict[str, Any] = Field(default_factory=dict)


class EmbeddingTaskStatus(BaseModel):
    task_id: str
    completed: bool
    failed: bool = False
    error: str | None = None
    raw_response: dict[str, Any] = Field(default_factory=dict)


class EmbeddingDispatchRunResult(BaseModel):
    queue_status: EmbeddingQueueSnapshot
    submitted_task_id: str | None = None
    completed_task_ids: list[str] = Field(default_factory=list)
    failed_task_ids: list[str] = Field(default_factory=list)
