from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DocumentElement(BaseModel):
    element_id: str
    type: str
    page_number: int | None = None
    text: str | None = None
    markdown: str | None = None
    html: str | None = None
    bbox: dict[str, Any] | None = None
    confidence: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
