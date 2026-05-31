from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.docling.docling_formats import (
    VLM_SUPPORTED_FORMATS,
)
from ingest_orquestator_server.infrastructure.docling.docling_options import (
    build_convert_pipeline_options,
    build_pdf_pipeline_options,
    build_vlm_pipeline_options,
)


@dataclass(frozen=True)
class DoclingFormatRoute:
    input_format: str
    format_option_class: str
    pipeline_class: str
    backend_class: str
    route_kind: str
    supports_vlm: bool = False

    def to_metadata(self, *, selected_pipeline: str) -> dict[str, Any]:
        return {
            "input_format": self.input_format,
            "selected_pipeline": selected_pipeline,
            "format_option": self.format_option_class,
            "pipeline_class": self.pipeline_class,
            "backend_class": self.backend_class,
            "route_kind": self.route_kind,
            "supports_vlm": self.supports_vlm,
        }


def build_format_options(
    settings: Settings,
    *,
    pipeline: str,
    input_format: str | None,
) -> tuple[list[Any], dict[Any, Any], dict[str, DoclingFormatRoute]]:
    try:
        from docling.backend.json.docling_json_backend import DoclingJSONBackend
        from docling.backend.webvtt_backend import WebVTTDocumentBackend
        from docling.datamodel.backend_options import XBRLBackendOptions
        from docling.datamodel.base_models import InputFormat
        from docling.document_converter import (
            AsciiDocFormatOption,
            AudioFormatOption,
            CsvFormatOption,
            ExcelFormatOption,
            FormatOption,
            HTMLFormatOption,
            ImageFormatOption,
            LatexFormatOption,
            MarkdownFormatOption,
            MetsGbsFormatOption,
            PatentUsptoFormatOption,
            PdfFormatOption,
            PowerpointFormatOption,
            WordFormatOption,
            XBRLFormatOption,
            XMLJatsFormatOption,
        )
        from docling.pipeline.simple_pipeline import SimplePipeline
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

    allowed_formats = [
        InputFormat(format_name) for format_name in settings.docling_allowed_formats
    ]
    convert_options = build_convert_pipeline_options(settings)
    standard_pdf_options = None
    vlm_options = None
    format_options: dict[Any, Any] = {}
    routes: dict[str, DoclingFormatRoute] = {}

    for fmt in settings.docling_allowed_formats:
        docling_format = InputFormat(fmt)
        selected_pipeline = pipeline if input_format in {None, fmt} else "standard"

        if selected_pipeline == "vlm" and fmt in VLM_SUPPORTED_FORMATS:
            if vlm_options is None:
                vlm_options = build_vlm_pipeline_options(settings)
            option_cls = PdfFormatOption if fmt == "pdf" else ImageFormatOption
            format_options[docling_format] = option_cls(
                pipeline_cls=IngestProgressVlmPipeline,
                pipeline_options=vlm_options,
            )
            routes[fmt] = DoclingFormatRoute(
                input_format=fmt,
                format_option_class=option_cls.__name__,
                pipeline_class=IngestProgressVlmPipeline.__name__,
                backend_class=format_options[docling_format].backend.__name__,
                route_kind="vlm",
                supports_vlm=True,
            )
            continue

        if fmt in {"pdf", "image"}:
            if standard_pdf_options is None:
                standard_pdf_options = build_pdf_pipeline_options(settings)
            option_cls = PdfFormatOption if fmt == "pdf" else ImageFormatOption
            format_options[docling_format] = option_cls(
                pipeline_cls=IngestProgressStandardPdfPipeline,
                pipeline_options=standard_pdf_options,
            )
            routes[fmt] = DoclingFormatRoute(
                input_format=fmt,
                format_option_class=option_cls.__name__,
                pipeline_class=IngestProgressStandardPdfPipeline.__name__,
                backend_class=format_options[docling_format].backend.__name__,
                route_kind="standard",
                supports_vlm=True,
            )
            continue

        if fmt == "xml_xbrl":
            format_options[docling_format] = XBRLFormatOption(
                pipeline_options=convert_options,
                backend_options=XBRLBackendOptions(
                    enable_local_fetch=settings.docling_xbrl_enable_local_fetch,
                    enable_remote_fetch=settings.docling_xbrl_enable_remote_fetch,
                    taxonomy=settings.docling_xbrl_taxonomy_path,
                ),
            )
            routes[fmt] = _route_from_option(fmt, format_options[docling_format], "simple")
            continue

        option_cls_by_format = {
            "docx": WordFormatOption,
            "pptx": PowerpointFormatOption,
            "html": HTMLFormatOption,
            "md": MarkdownFormatOption,
            "asciidoc": AsciiDocFormatOption,
            "csv": CsvFormatOption,
            "xlsx": ExcelFormatOption,
            "latex": LatexFormatOption,
            "xml_jats": XMLJatsFormatOption,
            "xml_uspto": PatentUsptoFormatOption,
        }
        option_cls = option_cls_by_format.get(fmt)
        if option_cls is not None:
            format_options[docling_format] = option_cls(pipeline_options=convert_options)
            routes[fmt] = _route_from_option(fmt, format_options[docling_format], "simple")
            continue

        if fmt == "json_docling":
            format_options[docling_format] = FormatOption(
                pipeline_cls=SimplePipeline,
                backend=DoclingJSONBackend,
                pipeline_options=convert_options,
            )
            routes[fmt] = _route_from_option(fmt, format_options[docling_format], "simple")
            continue

        if fmt == "vtt":
            format_options[docling_format] = FormatOption(
                pipeline_cls=SimplePipeline,
                backend=WebVTTDocumentBackend,
                pipeline_options=convert_options,
            )
            routes[fmt] = _route_from_option(fmt, format_options[docling_format], "simple")
            continue

        if fmt == "mets_gbs":
            if standard_pdf_options is None:
                standard_pdf_options = build_pdf_pipeline_options(settings)
            format_options[docling_format] = MetsGbsFormatOption(
                pipeline_cls=IngestProgressStandardPdfPipeline,
                pipeline_options=standard_pdf_options,
            )
            routes[fmt] = _route_from_option(fmt, format_options[docling_format], "standard")
            continue

        if fmt == "audio":
            format_options[docling_format] = AudioFormatOption()
            routes[fmt] = _route_from_option(fmt, format_options[docling_format], "asr")

    return allowed_formats, format_options, routes


def route_metadata_for(
    *,
    input_format: str,
    pipeline: str,
) -> dict[str, Any]:
    if pipeline == "vlm" and input_format in VLM_SUPPORTED_FORMATS:
        return DoclingFormatRoute(
            input_format=input_format,
            format_option_class="PdfFormatOption"
            if input_format == "pdf"
            else "ImageFormatOption",
            pipeline_class="IngestProgressVlmPipeline",
            backend_class="DoclingParseDocumentBackend"
            if input_format == "pdf"
            else "ImageDocumentBackend",
            route_kind="vlm",
            supports_vlm=True,
        ).to_metadata(selected_pipeline=pipeline)
    if input_format in {"pdf", "image"}:
        return DoclingFormatRoute(
            input_format=input_format,
            format_option_class="PdfFormatOption"
            if input_format == "pdf"
            else "ImageFormatOption",
            pipeline_class="IngestProgressStandardPdfPipeline",
            backend_class="DoclingParseDocumentBackend"
            if input_format == "pdf"
            else "ImageDocumentBackend",
            route_kind="standard",
            supports_vlm=True,
        ).to_metadata(selected_pipeline=pipeline)
    simple_routes = {
        "docx": ("WordFormatOption", "MsWordDocumentBackend"),
        "pptx": ("PowerpointFormatOption", "MsPowerpointDocumentBackend"),
        "html": ("HTMLFormatOption", "HTMLDocumentBackend"),
        "md": ("MarkdownFormatOption", "MarkdownDocumentBackend"),
        "asciidoc": ("AsciiDocFormatOption", "AsciiDocBackend"),
        "csv": ("CsvFormatOption", "CsvDocumentBackend"),
        "xlsx": ("ExcelFormatOption", "MsExcelDocumentBackend"),
        "latex": ("LatexFormatOption", "LatexDocumentBackend"),
        "json_docling": ("FormatOption", "DoclingJSONBackend"),
        "xml_xbrl": ("XBRLFormatOption", "XBRLDocumentBackend"),
        "xml_jats": ("XMLJatsFormatOption", "JatsDocumentBackend"),
        "xml_uspto": ("PatentUsptoFormatOption", "PatentUsptoDocumentBackend"),
        "vtt": ("FormatOption", "WebVTTDocumentBackend"),
    }
    format_option, backend = simple_routes.get(
        input_format,
        ("DoclingDefaultFormatOption", "DoclingDefaultBackend"),
    )
    return DoclingFormatRoute(
        input_format=input_format,
        format_option_class=format_option,
        pipeline_class="SimplePipeline",
        backend_class=backend,
        route_kind="simple",
    ).to_metadata(selected_pipeline=pipeline)


def _route_from_option(
    input_format: str,
    option: Any,
    route_kind: str,
) -> DoclingFormatRoute:
    return DoclingFormatRoute(
        input_format=input_format,
        format_option_class=type(option).__name__,
        pipeline_class=option.pipeline_cls.__name__,
        backend_class=option.backend.__name__,
        route_kind=route_kind,
        supports_vlm=False,
    )
