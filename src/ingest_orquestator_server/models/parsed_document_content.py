from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ingest_orquestator_server.models.rag_ingestion import RagIngestionRecord


class ParsedDocumentContent(BaseModel):
    document_id: str
    markdown: str
    html: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    rag_records: list[RagIngestionRecord] = Field(default_factory=list)
