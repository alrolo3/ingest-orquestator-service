from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class RagRecordType(StrEnum):
    CHUNK = "chunk"
    DOCUMENT = "document"


class RagIngestionRecord(BaseModel):
    schema_version: str = "1.0"
    record_id: str
    document_id: str
    job_id: str
    content: str
    title: str | None = None
    source_file_name: str | None = None
    input_format: str | None = None
    parser: str | None = None
    pipeline: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    chunk_id: str | None = None
    record_type: RagRecordType = RagRecordType.CHUNK
    metadata: dict[str, Any] = Field(default_factory=dict)
