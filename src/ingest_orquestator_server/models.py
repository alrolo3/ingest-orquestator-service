from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class IngestionStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentPage(BaseModel):
    page_number: int
    width: float | None = None
    height: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


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


class ParsedDocument(BaseModel):
    document_id: str
    source_file_name: str
    source_path: str
    mime_type: str | None = None
    title: str | None = None
    page_count: int = 0
    pages: list[DocumentPage] = Field(default_factory=list)
    elements: list[DocumentElement] = Field(default_factory=list)
    markdown: str = ""
    text: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ParseOutput(BaseModel):
    document: ParsedDocument
    raw_docling: dict[str, Any]
    raw_markdown: str
    raw_text: str
    raw_html: str | None = None


class OutputFiles(BaseModel):
    model_config = ConfigDict(json_encoders={Path: str})

    output_dir: Path
    raw_docling_json: Path
    normalized_json: Path
    markdown: Path
    text: Path
    html: Path | None = None
    manifest_json: Path


class IngestResponse(BaseModel):
    job_id: str
    status: IngestionStatus
    parser: str
    document_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    input_path: Path
    outputs: OutputFiles
    document: ParsedDocument | None = None
    error: str | None = None
