from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EmbeddingRecord(BaseModel):
    record_id: str
    document_id: str
    chunk_id: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
