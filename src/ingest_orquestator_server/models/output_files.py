from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict


class OutputFiles(BaseModel):
    model_config = ConfigDict(json_encoders={Path: str})

    output_dir: Path
    markdown: Path
    document_metadata_json: Path | None = None
    rag_chunks_jsonl: Path | None = None
    html: Path | None = None
    raw_docling_json: Path | None = None
    normalized_json: Path | None = None
    text: Path | None = None
    chunks_json: Path | None = None
    embedding_input_jsonl: Path | None = None
    confidence_json: Path | None = None
    manifest_json: Path | None = None
