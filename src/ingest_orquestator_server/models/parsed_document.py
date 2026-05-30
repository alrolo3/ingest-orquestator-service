from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ingest_orquestator_server.models.document_element import DocumentElement
from ingest_orquestator_server.models.document_page import DocumentPage


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
