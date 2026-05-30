from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from ingest_orquestator_server.models.parsed_document import ParsedDocument


class ParseOutput(BaseModel):
    document: ParsedDocument
    raw_docling: dict[str, Any]
    raw_markdown: str
    raw_text: str
    raw_html: str | None = None
