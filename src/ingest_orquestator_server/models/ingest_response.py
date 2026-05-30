from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from ingest_orquestator_server.models.document_chunk import DocumentChunk
from ingest_orquestator_server.models.ingestion_status import IngestionStatus
from ingest_orquestator_server.models.output_files import OutputFiles
from ingest_orquestator_server.models.parsed_document import ParsedDocument


class IngestResponse(BaseModel):
    job_id: str
    status: IngestionStatus
    parser: str
    document_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    input_path: Path
    outputs: OutputFiles
    document: ParsedDocument | None = None
    chunks: list[DocumentChunk] | None = None
    error: str | None = None
