from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ParseDiagnostics(BaseModel):
    parser: str
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    chunk_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
