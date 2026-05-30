from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    chunk_id: str
    document_id: str
    page_start: int | None = None
    page_end: int | None = None
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
