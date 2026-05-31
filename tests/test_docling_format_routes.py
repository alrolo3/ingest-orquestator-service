from docling.datamodel.base_models import InputFormat
from docling.pipeline.simple_pipeline import SimplePipeline
from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
from docling.pipeline.vlm_pipeline import VlmPipeline

from ingest_orquestator_server.config import Settings
from ingest_orquestator_server.infrastructure.docling.docling_format_routes import (
    build_format_options,
    route_metadata_for,
)


def test_build_format_options_routes_default_formats_without_model_loading() -> None:
    settings = Settings(docling_pdf_ocr_engine="auto")

    allowed_formats, format_options, routes = build_format_options(
        settings,
        pipeline="standard",
        input_format="md",
    )

    assert {input_format.value for input_format in allowed_formats} == set(
        settings.docling_allowed_formats
    )
    assert {input_format.value for input_format in format_options} == set(
        settings.docling_allowed_formats
    )
    assert set(routes) == set(settings.docling_allowed_formats)
    assert issubclass(format_options[InputFormat.PDF].pipeline_cls, StandardPdfPipeline)
    assert issubclass(format_options[InputFormat.IMAGE].pipeline_cls, StandardPdfPipeline)
    assert issubclass(format_options[InputFormat.MD].pipeline_cls, SimplePipeline)
    assert routes["pdf"].route_kind == "standard"
    assert routes["md"].route_kind == "simple"


def test_build_format_options_routes_selected_vlm_format_only() -> None:
    settings = Settings(
        docling_allowed_formats=["docx", "image", "pdf"],
        docling_pdf_ocr_engine="auto",
        docling_vlm_runtime="remote_llm",
    )

    _allowed_formats, format_options, routes = build_format_options(
        settings,
        pipeline="vlm",
        input_format="pdf",
    )

    assert issubclass(format_options[InputFormat.PDF].pipeline_cls, VlmPipeline)
    assert issubclass(format_options[InputFormat.IMAGE].pipeline_cls, StandardPdfPipeline)
    assert issubclass(format_options[InputFormat.DOCX].pipeline_cls, SimplePipeline)
    assert routes["pdf"].route_kind == "vlm"
    assert routes["image"].route_kind == "standard"
    assert routes["docx"].route_kind == "simple"


def test_route_metadata_records_docling_converter_classes() -> None:
    assert route_metadata_for(input_format="pdf", pipeline="vlm") == {
        "input_format": "pdf",
        "selected_pipeline": "vlm",
        "format_option": "PdfFormatOption",
        "pipeline_class": "IngestProgressVlmPipeline",
        "backend_class": "DoclingParseDocumentBackend",
        "route_kind": "vlm",
        "supports_vlm": True,
    }
    assert route_metadata_for(input_format="docx", pipeline="standard") == {
        "input_format": "docx",
        "selected_pipeline": "standard",
        "format_option": "WordFormatOption",
        "pipeline_class": "SimplePipeline",
        "backend_class": "MsWordDocumentBackend",
        "route_kind": "simple",
        "supports_vlm": False,
    }
