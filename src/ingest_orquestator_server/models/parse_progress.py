from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ParseProgressUpdate:
    component: str
    stage: str
    message: str | None = None
    input_format: str | None = None
    pipeline: str | None = None
    page_count: int | None = None
    pages_completed: int | None = None
    current_page: int | None = None
    details: Mapping[str, Any] | None = None


ParseProgressCallback = Callable[[ParseProgressUpdate], None]
