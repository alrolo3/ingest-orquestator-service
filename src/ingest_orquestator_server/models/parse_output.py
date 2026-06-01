from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ingest_orquestator_server.models.parsed_document import ParsedDocument


class ParseOutput(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    document_id: str
    source_file_name: str | None = None
    title: str | None = None
    markdown: str
    html: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    normalized_document: ParsedDocument | None = Field(default=None, exclude=True)
    chunking_document: Any | None = Field(default=None, exclude=True)
    conversion_status: str | None = None
    conversion_errors: list[Any] = Field(default_factory=list)
    conversion_timings: dict[str, Any] = Field(default_factory=dict)
    confidence_summary: dict[str, Any] = Field(default_factory=dict)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
