from __future__ import annotations

from collections.abc import Callable
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


@dataclass(frozen=True)
class _FormatRouteSpec:
    input_format: str
    format_option_class: str
    pipeline_class: str
    backend_class: str
    route_kind: str
    option_builder: str
    supports_vlm: bool = False
    emits_route_metadata: bool = True

    def to_route(self) -> DoclingFormatRoute:
        return DoclingFormatRoute(
            input_format=self.input_format,
            format_option_class=self.format_option_class,
            pipeline_class=self.pipeline_class,
            backend_class=self.backend_class,
            route_kind=self.route_kind,
            supports_vlm=self.supports_vlm,
        )


_STANDARD_ROUTE_SPECS = {
    "pdf": _FormatRouteSpec(
        input_format="pdf",
        format_option_class="PdfFormatOption",
        pipeline_class="IngestProgressStandardPdfPipeline",
        backend_class="ThreadedDoclingParseDocumentBackend",
        route_kind="standard",
        option_builder="pdf_pipeline",
        supports_vlm=True,
    ),
    "image": _FormatRouteSpec(
        input_format="image",
        format_option_class="ImageFormatOption",
        pipeline_class="IngestProgressStandardPdfPipeline",
        backend_class="ImageDocumentBackend",
        route_kind="standard",
        option_builder="pdf_pipeline",
        supports_vlm=True,
    ),
    "docx": _FormatRouteSpec(
        input_format="docx",
        format_option_class="WordFormatOption",
        pipeline_class="SimplePipeline",
        backend_class="MsWordDocumentBackend",
        route_kind="simple",
        option_builder="convert_pipeline",
    ),
    "pptx": _FormatRouteSpec(
        input_format="pptx",
        format_option_class="PowerpointFormatOption",
        pipeline_class="SimplePipeline",
        backend_class="MsPowerpointDocumentBackend",
        route_kind="simple",
        option_builder="convert_pipeline",
    ),
    "html": _FormatRouteSpec(
        input_format="html",
        format_option_class="HTMLFormatOption",
        pipeline_class="SimplePipeline",
        backend_class="HTMLDocumentBackend",
        route_kind="simple",
        option_builder="convert_pipeline",
    ),
    "md": _FormatRouteSpec(
        input_format="md",
        format_option_class="MarkdownFormatOption",
        pipeline_class="SimplePipeline",
        backend_class="MarkdownDocumentBackend",
        route_kind="simple",
        option_builder="convert_pipeline",
    ),
    "asciidoc": _FormatRouteSpec(
        input_format="asciidoc",
        format_option_class="AsciiDocFormatOption",
        pipeline_class="SimplePipeline",
        backend_class="AsciiDocBackend",
        route_kind="simple",
        option_builder="convert_pipeline",
    ),
    "csv": _FormatRouteSpec(
        input_format="csv",
        format_option_class="CsvFormatOption",
        pipeline_class="SimplePipeline",
        backend_class="CsvDocumentBackend",
        route_kind="simple",
        option_builder="convert_pipeline",
    ),
    "xlsx": _FormatRouteSpec(
        input_format="xlsx",
        format_option_class="ExcelFormatOption",
        pipeline_class="SimplePipeline",
        backend_class="MsExcelDocumentBackend",
        route_kind="simple",
        option_builder="convert_pipeline",
    ),
    "latex": _FormatRouteSpec(
        input_format="latex",
        format_option_class="LatexFormatOption",
        pipeline_class="SimplePipeline",
        backend_class="LatexDocumentBackend",
        route_kind="simple",
        option_builder="convert_pipeline",
    ),
    "xml_jats": _FormatRouteSpec(
        input_format="xml_jats",
        format_option_class="XMLJatsFormatOption",
        pipeline_class="SimplePipeline",
        backend_class="JatsDocumentBackend",
        route_kind="simple",
        option_builder="convert_pipeline",
    ),
    "xml_uspto": _FormatRouteSpec(
        input_format="xml_uspto",
        format_option_class="PatentUsptoFormatOption",
        pipeline_class="SimplePipeline",
        backend_class="PatentUsptoDocumentBackend",
        route_kind="simple",
        option_builder="convert_pipeline",
    ),
    "json_docling": _FormatRouteSpec(
        input_format="json_docling",
        format_option_class="FormatOption",
        pipeline_class="SimplePipeline",
        backend_class="DoclingJSONBackend",
        route_kind="simple",
        option_builder="backend_pipeline",
    ),
    "vtt": _FormatRouteSpec(
        input_format="vtt",
        format_option_class="FormatOption",
        pipeline_class="SimplePipeline",
        backend_class="WebVTTDocumentBackend",
        route_kind="simple",
        option_builder="backend_pipeline",
    ),
    "xml_xbrl": _FormatRouteSpec(
        input_format="xml_xbrl",
        format_option_class="XBRLFormatOption",
        pipeline_class="SimplePipeline",
        backend_class="XBRLDocumentBackend",
        route_kind="simple",
        option_builder="xbrl_pipeline",
    ),
    "mets_gbs": _FormatRouteSpec(
        input_format="mets_gbs",
        format_option_class="MetsGbsFormatOption",
        pipeline_class="IngestProgressStandardPdfPipeline",
        backend_class="MetsGbsDocumentBackend",
        route_kind="standard",
        option_builder="pdf_pipeline",
        emits_route_metadata=False,
    ),
    "audio": _FormatRouteSpec(
        input_format="audio",
        format_option_class="AudioFormatOption",
        pipeline_class="AsrPipeline",
        backend_class="NoOpBackend",
        route_kind="asr",
        option_builder="audio_pipeline",
        emits_route_metadata=False,
    ),
}

_VLM_ROUTE_SPECS = {
    "pdf": _FormatRouteSpec(
        input_format="pdf",
        format_option_class="PdfFormatOption",
        pipeline_class="IngestProgressVlmPipeline",
        backend_class="DoclingParseDocumentBackend",
        route_kind="vlm",
        option_builder="vlm_pipeline",
        supports_vlm=True,
    ),
    "image": _FormatRouteSpec(
        input_format="image",
        format_option_class="ImageFormatOption",
        pipeline_class="IngestProgressVlmPipeline",
        backend_class="ImageDocumentBackend",
        route_kind="vlm",
        option_builder="vlm_pipeline",
        supports_vlm=True,
    ),
}


def build_format_options(
    settings: Settings,
    *,
    pipeline: str,
    input_format: str | None,
) -> tuple[list[Any], dict[Any, Any], dict[str, DoclingFormatRoute]]:
    try:
        from docling.backend.docling_parse_backend import (
            DoclingParseDocumentBackend,
            ThreadedDoclingParseDocumentBackend,
        )
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

    docling_classes = {
        "AsciiDocFormatOption": AsciiDocFormatOption,
        "AudioFormatOption": AudioFormatOption,
        "CsvFormatOption": CsvFormatOption,
        "DoclingJSONBackend": DoclingJSONBackend,
        "ExcelFormatOption": ExcelFormatOption,
        "FormatOption": FormatOption,
        "HTMLFormatOption": HTMLFormatOption,
        "ImageFormatOption": ImageFormatOption,
        "IngestProgressStandardPdfPipeline": IngestProgressStandardPdfPipeline,
        "IngestProgressVlmPipeline": IngestProgressVlmPipeline,
        "LatexFormatOption": LatexFormatOption,
        "MarkdownFormatOption": MarkdownFormatOption,
        "MetsGbsFormatOption": MetsGbsFormatOption,
        "PatentUsptoFormatOption": PatentUsptoFormatOption,
        "PdfFormatOption": PdfFormatOption,
        "PowerpointFormatOption": PowerpointFormatOption,
        "SimplePipeline": SimplePipeline,
        "DoclingParseDocumentBackend": DoclingParseDocumentBackend,
        "ThreadedDoclingParseDocumentBackend": ThreadedDoclingParseDocumentBackend,
        "WebVTTDocumentBackend": WebVTTDocumentBackend,
        "WordFormatOption": WordFormatOption,
        "XBRLBackendOptions": XBRLBackendOptions,
        "XBRLFormatOption": XBRLFormatOption,
        "XMLJatsFormatOption": XMLJatsFormatOption,
    }

    allowed_formats = [
        InputFormat(format_name) for format_name in settings.docling_allowed_formats
    ]
    convert_options = build_convert_pipeline_options(settings)
    standard_pdf_options = None
    vlm_options = None
    format_options: dict[Any, Any] = {}
    routes: dict[str, DoclingFormatRoute] = {}

    def get_standard_pdf_options() -> Any:
        nonlocal standard_pdf_options
        if standard_pdf_options is None:
            standard_pdf_options = build_pdf_pipeline_options(settings)
        return standard_pdf_options

    def get_vlm_options() -> Any:
        nonlocal vlm_options
        if vlm_options is None:
            vlm_options = build_vlm_pipeline_options(settings)
        return vlm_options

    for fmt in settings.docling_allowed_formats:
        docling_format = InputFormat(fmt)
        selected_pipeline = pipeline if input_format in {None, fmt} else "standard"
        route_spec = _route_spec_for(input_format=fmt, pipeline=selected_pipeline)
        if route_spec.option_builder == "default":
            continue
        format_options[docling_format] = _build_format_option(
            route_spec,
            classes=docling_classes,
            convert_options=convert_options,
            get_standard_pdf_options=get_standard_pdf_options,
            get_vlm_options=get_vlm_options,
            settings=settings,
        )
        routes[fmt] = route_spec.to_route()

    return allowed_formats, format_options, routes


def route_metadata_for(
    *,
    input_format: str,
    pipeline: str,
) -> dict[str, Any]:
    return _metadata_route_spec_for(
        input_format=input_format,
        pipeline=pipeline,
    ).to_route().to_metadata(selected_pipeline=pipeline)


def _route_spec_for(
    input_format: str,
    pipeline: str,
) -> _FormatRouteSpec:
    if pipeline == "vlm" and input_format in VLM_SUPPORTED_FORMATS:
        return _VLM_ROUTE_SPECS[input_format]
    route_spec = _STANDARD_ROUTE_SPECS.get(input_format)
    if route_spec is not None:
        return route_spec
    return _default_route_spec(input_format)


def _metadata_route_spec_for(
    input_format: str,
    pipeline: str,
) -> _FormatRouteSpec:
    route_spec = _route_spec_for(input_format=input_format, pipeline=pipeline)
    if route_spec.emits_route_metadata:
        return route_spec
    # Preserve the legacy public metadata fallback for build-only configured routes.
    return _default_route_spec(input_format)


def _default_route_spec(input_format: str) -> _FormatRouteSpec:
    return _FormatRouteSpec(
        input_format=input_format,
        format_option_class="DoclingDefaultFormatOption",
        pipeline_class="SimplePipeline",
        backend_class="DoclingDefaultBackend",
        route_kind="simple",
        option_builder="default",
    )


def _build_format_option(
    route_spec: _FormatRouteSpec,
    *,
    classes: dict[str, Any],
    convert_options: Any,
    get_standard_pdf_options: Callable[[], Any],
    get_vlm_options: Callable[[], Any],
    settings: Settings,
) -> Any:
    option_cls = classes[route_spec.format_option_class]
    if route_spec.option_builder == "pdf_pipeline":
        kwargs = {
            "pipeline_cls": classes[route_spec.pipeline_class],
            "pipeline_options": get_standard_pdf_options(),
        }
        if route_spec.format_option_class == "PdfFormatOption":
            kwargs["backend"] = classes[route_spec.backend_class]
        return option_cls(**kwargs)
    if route_spec.option_builder == "vlm_pipeline":
        kwargs = {
            "pipeline_cls": classes[route_spec.pipeline_class],
            "pipeline_options": get_vlm_options(),
        }
        if route_spec.format_option_class == "PdfFormatOption":
            kwargs["backend"] = classes[route_spec.backend_class]
        return option_cls(**kwargs)
    if route_spec.option_builder == "convert_pipeline":
        return option_cls(pipeline_options=convert_options)
    if route_spec.option_builder == "backend_pipeline":
        return option_cls(
            pipeline_cls=classes[route_spec.pipeline_class],
            backend=classes[route_spec.backend_class],
            pipeline_options=convert_options,
        )
    if route_spec.option_builder == "xbrl_pipeline":
        xbrl_backend_options_cls = classes["XBRLBackendOptions"]
        return option_cls(
            pipeline_options=convert_options,
            backend_options=xbrl_backend_options_cls(
                enable_local_fetch=settings.docling_xbrl_enable_local_fetch,
                enable_remote_fetch=settings.docling_xbrl_enable_remote_fetch,
                taxonomy=settings.docling_xbrl_taxonomy_path,
            ),
        )
    if route_spec.option_builder == "audio_pipeline":
        return option_cls()
    raise ValueError(f"Unknown Docling route option builder '{route_spec.option_builder}'.")
