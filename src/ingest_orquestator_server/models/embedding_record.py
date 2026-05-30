from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EmbeddingRecord(BaseModel):
    schema_version: str = "1.3"
    record_id: str
    document_id: str
    chunk_id: str
    text: str
    raw_text: str | None = None
    contextualized: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
