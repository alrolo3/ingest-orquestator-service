from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ingest_orquestator_server.models.parsed_document import ParsedDocument


class ParseOutput(BaseModel):
    document: ParsedDocument
    raw_docling: dict[str, Any]
    raw_markdown: str
    raw_text: str
    raw_html: str | None = None
    docling_document: Any | None = None
    conversion_status: str | None = None
    conversion_errors: list[Any] = Field(default_factory=list)
    conversion_timings: dict[str, Any] = Field(default_factory=dict)
    confidence: dict[str, Any] | None = None
    confidence_summary: dict[str, Any] = Field(default_factory=dict)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
