from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict


class OutputFiles(BaseModel):
    model_config = ConfigDict(json_encoders={Path: str})

    output_dir: Path
    raw_docling_json: Path
    normalized_json: Path
    markdown: Path
    text: Path
    html: Path | None = None
    chunks_json: Path | None = None
    manifest_json: Path
