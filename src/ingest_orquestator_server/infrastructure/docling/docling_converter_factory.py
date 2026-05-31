from __future__ import annotations

from typing import Any

from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.docling.docling_formats import (
    validate_allowed_format,
)
from ingest_orquestator_server.infrastructure.docling.docling_options import (
    build_convert_pipeline_options,
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
            from docling.datamodel.backend_options import XBRLBackendOptions
            from docling.datamodel.base_models import InputFormat
            from docling.document_converter import (
                DocumentConverter,
                ImageFormatOption,
                PdfFormatOption,
                XBRLFormatOption,
            )
            from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
            from docling.pipeline.vlm_pipeline import VlmPipeline
        except ImportError as exc:
            raise RuntimeError(
                "Docling is not installed. Install project dependencies with "
                "`python -m pip install -e .` inside the project virtual environment."
            ) from exc

        from ingest_orquestator_server.infrastructure.docling.progress_pipelines import (
            ProgressStandardPdfPipeline,
            ProgressVlmPipeline,
        )

        class IngestProgressStandardPdfPipeline(
            ProgressStandardPdfPipeline,
            StandardPdfPipeline,
        ):
            pass

        class IngestProgressVlmPipeline(ProgressVlmPipeline, VlmPipeline):
            pass

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
                    pipeline_cls=IngestProgressVlmPipeline,
                    pipeline_options=vlm_pipeline_options,
                )
            if input_format in {None, "image"}:
                format_options[InputFormat.IMAGE] = ImageFormatOption(
                    pipeline_cls=IngestProgressVlmPipeline,
                    pipeline_options=vlm_pipeline_options,
                )
        else:
            standard_pipeline_options = None
            if input_format in {None, "pdf"}:
                standard_pipeline_options = build_pdf_pipeline_options(settings)
                format_options[InputFormat.PDF] = PdfFormatOption(
                    pipeline_cls=IngestProgressStandardPdfPipeline,
                    pipeline_options=standard_pipeline_options,
                )
            if input_format in {None, "image"}:
                if standard_pipeline_options is None:
                    standard_pipeline_options = build_pdf_pipeline_options(settings)
                format_options[InputFormat.IMAGE] = ImageFormatOption(
                    pipeline_cls=IngestProgressStandardPdfPipeline,
                    pipeline_options=standard_pipeline_options,
                )
            if input_format in {None, "xml_xbrl"}:
                format_options[InputFormat.XML_XBRL] = XBRLFormatOption(
                    pipeline_options=build_convert_pipeline_options(settings),
                    backend_options=XBRLBackendOptions(
                        enable_local_fetch=settings.docling_xbrl_enable_local_fetch,
                        enable_remote_fetch=settings.docling_xbrl_enable_remote_fetch,
                        taxonomy=settings.docling_xbrl_taxonomy_path,
                    ),
                )

        return DocumentConverter(
            allowed_formats=allowed_formats,
            format_options=format_options,
        )
