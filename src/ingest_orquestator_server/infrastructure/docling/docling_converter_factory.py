from __future__ import annotations

from typing import Any

from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.docling.docling_format_routes import (
    build_format_options,
)
from ingest_orquestator_server.infrastructure.docling.docling_formats import (
    validate_allowed_format,
)


class DoclingConverterFactory:
    def create(
        self,
        settings: Settings,
        *,
        pipeline: str = "standard",
        input_format: str | None = None,
    ) -> Any:
        try:
            from docling.document_converter import DocumentConverter
        except ImportError as exc:
            raise RuntimeError(
                "Docling is not installed. Install project dependencies with "
                "`python -m pip install -e .` inside the project virtual environment."
            ) from exc

        if input_format is not None:
            validate_allowed_format(input_format, settings.docling_allowed_formats)

        allowed_formats, format_options, _routes = build_format_options(
            settings,
            pipeline=pipeline,
            input_format=input_format,
        )

        return DocumentConverter(
            allowed_formats=allowed_formats,
            format_options=format_options,
        )
