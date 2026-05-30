from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any
from uuid import uuid4

from ingest_orquestator_server.models import ParseOutput
from ingest_orquestator_server.normalization import normalize_docling_document


class DoclingParser:
    name = "docling"

    def __init__(self, converter: Any | None = None) -> None:
        self._converter = converter

    def parse(self, file_path: Path, *, document_id: str | None = None) -> ParseOutput:
        source_path = file_path.expanduser().resolve()
        if not source_path.is_file():
            raise FileNotFoundError(f"Input file does not exist: {source_path}")

        converter = self._converter or self._create_converter()
        result = converter.convert(source_path)
        document = result.document
        raw_docling = document.export_to_dict()
        raw_markdown = document.export_to_markdown()
        raw_text = document.export_to_text()
        raw_html = _try_export_html(document)
        mime_type = mimetypes.guess_type(source_path.name)[0]
        resolved_document_id = document_id or str(uuid4())

        normalized = normalize_docling_document(
            raw_docling=raw_docling,
            source_path=source_path,
            document_id=resolved_document_id,
            markdown=raw_markdown,
            text=raw_text,
            mime_type=mime_type,
        )

        return ParseOutput(
            document=normalized,
            raw_docling=raw_docling,
            raw_markdown=raw_markdown,
            raw_text=raw_text,
            raw_html=raw_html,
        )

    @staticmethod
    def _create_converter() -> Any:
        try:
            from docling.document_converter import DocumentConverter
        except ImportError as exc:
            raise RuntimeError(
                "Docling is not installed. Install project dependencies with "
                "`uv sync --extra dev --python 3.12` or `pip install .`."
            ) from exc

        return DocumentConverter()


def _try_export_html(document: Any) -> str | None:
    export_to_html = getattr(document, "export_to_html", None)
    if export_to_html is None:
        return None

    try:
        return export_to_html()
    except Exception:
        return None
