from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DocumentPage(BaseModel):
    page_number: int
    width: float | None = None
    height: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
