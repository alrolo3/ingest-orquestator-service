from __future__ import annotations

from typing import Any

from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.docling.docling_formats import (
    validate_allowed_format,
)
from ingest_orquestator_server.infrastructure.docling.docling_options import (
    build_pdf_pipeline_options,
    build_vlm_pipeline_options,
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
            from docling.datamodel.base_models import InputFormat
            from docling.document_converter import (
                DocumentConverter,
                ImageFormatOption,
                PdfFormatOption,
            )
            from docling.pipeline.vlm_pipeline import VlmPipeline
        except ImportError as exc:
            raise RuntimeError(
                "Docling is not installed. Install project dependencies with "
                "`python -m pip install -e .` inside the project virtual environment."
            ) from exc

        if input_format is not None:
            validate_allowed_format(input_format, settings.docling_allowed_formats)

        allowed_formats = [
            InputFormat(format_name) for format_name in settings.docling_allowed_formats
        ]
        format_options: dict[Any, Any] = {}
        if pipeline == "vlm":
            vlm_pipeline_options = build_vlm_pipeline_options(settings)
            if input_format in {None, "pdf"}:
                format_options[InputFormat.PDF] = PdfFormatOption(
                    pipeline_cls=VlmPipeline,
                    pipeline_options=vlm_pipeline_options,
                )
            if input_format in {None, "image"}:
                format_options[InputFormat.IMAGE] = ImageFormatOption(
                    pipeline_cls=VlmPipeline,
                    pipeline_options=vlm_pipeline_options,
                )
        elif input_format in {None, "pdf"}:
            format_options[InputFormat.PDF] = PdfFormatOption(
                pipeline_options=build_pdf_pipeline_options(settings),
            )

        return DocumentConverter(
            allowed_formats=allowed_formats,
            format_options=format_options,
        )
