from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any
from uuid import uuid4

from ingest_orquestator_server.config.settings import Settings, get_settings
from ingest_orquestator_server.infrastructure.docling.docling_converter_factory import (
    DoclingConverterFactory,
)
from ingest_orquestator_server.infrastructure.docling.docling_options import (
    docling_options_metadata,
)
from ingest_orquestator_server.models.parse_output import ParseOutput
from ingest_orquestator_server.normalizers.docling.docling_document_normalizer import (
    DoclingDocumentNormalizer,
)


class DoclingDocumentParser:
    name = "docling"

    def __init__(
        self,
        *,
        converter: Any | None = None,
        converter_factory: DoclingConverterFactory | None = None,
        normalizer: DoclingDocumentNormalizer | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._converter = converter
        self._converter_factory = converter_factory or DoclingConverterFactory()
        self._normalizer = normalizer or DoclingDocumentNormalizer()
        self._settings = settings or get_settings()

    def parse(self, file_path: Path, *, document_id: str | None = None) -> ParseOutput:
        source_path = file_path.expanduser().resolve()
        if not source_path.is_file():
            raise FileNotFoundError(f"Input file does not exist: {source_path}")

        converter = self._converter or self._converter_factory.create(self._settings)
        result = converter.convert(source_path)
        document = result.document
        raw_docling = document.export_to_dict()
        raw_markdown = document.export_to_markdown()
        raw_text = document.export_to_text()
        raw_html = self._try_export_html(document)
        mime_type = mimetypes.guess_type(source_path.name)[0]
        resolved_document_id = document_id or str(uuid4())

        normalized = self._normalizer.normalize(
            raw_docling=raw_docling,
            source_path=source_path,
            document_id=resolved_document_id,
            markdown=raw_markdown,
            text=raw_text,
            mime_type=mime_type,
        )
        normalized.metadata["docling_options"] = docling_options_metadata(self._settings)

        return ParseOutput(
            document=normalized,
            raw_docling=raw_docling,
            raw_markdown=raw_markdown,
            raw_text=raw_text,
            raw_html=raw_html,
        )

    @staticmethod
    def _try_export_html(document: Any) -> str | None:
        export_to_html = getattr(document, "export_to_html", None)
        if export_to_html is None:
            return None

        try:
            return export_to_html()
        except Exception:
            return None
