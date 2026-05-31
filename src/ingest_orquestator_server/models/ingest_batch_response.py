from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from ingest_orquestator_server.models.ingest_response import IngestResponse


class IngestBatchResponse(BaseModel):
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    jobs: list[IngestResponse]
    failed: list[IngestResponse] = Field(default_factory=list)
