from __future__ import annotations

from typing import Any

from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.docling.docling_options import (
    build_pdf_pipeline_options,
)


class DoclingConverterFactory:
    def create(self, settings: Settings) -> Any:
        try:
            from docling.datamodel.base_models import InputFormat
            from docling.document_converter import DocumentConverter, PdfFormatOption
        except ImportError as exc:
            raise RuntimeError(
                "Docling is not installed. Install project dependencies with "
                "`uv sync --extra dev --python 3.12` or `pip install .`."
            ) from exc

        return DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=build_pdf_pipeline_options(settings),
                ),
            }
        )
