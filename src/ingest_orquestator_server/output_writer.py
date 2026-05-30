from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ingest_orquestator_server.models import OutputFiles, ParseOutput


def write_parse_output(parse_output: ParseOutput, output_root: Path) -> OutputFiles:
    document_id = parse_output.document.document_id
    output_dir = output_root / document_id
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_docling_json = output_dir / "raw_docling.json"
    normalized_json = output_dir / "normalized.json"
    markdown_path = output_dir / "document.md"
    text_path = output_dir / "document.txt"
    html_path = output_dir / "document.html" if parse_output.raw_html is not None else None
    manifest_json = output_dir / "manifest.json"

    _write_json(raw_docling_json, parse_output.raw_docling)
    normalized_json.write_text(parse_output.document.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(parse_output.raw_markdown, encoding="utf-8")
    text_path.write_text(parse_output.raw_text, encoding="utf-8")
    if html_path is not None:
        html_path.write_text(parse_output.raw_html or "", encoding="utf-8")

    files = OutputFiles(
        output_dir=output_dir,
        raw_docling_json=raw_docling_json,
        normalized_json=normalized_json,
        markdown=markdown_path,
        text=text_path,
        html=html_path,
        manifest_json=manifest_json,
    )
    _write_json(
        manifest_json,
        {
            "document_id": document_id,
            "source_file_name": parse_output.document.source_file_name,
            "source_path": parse_output.document.source_path,
            "outputs": files.model_dump(mode="json"),
        },
    )

    return files


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    content = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    path.write_text(content, encoding="utf-8")
