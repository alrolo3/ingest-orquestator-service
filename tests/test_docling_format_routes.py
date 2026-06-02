import pytest
from docling.datamodel.base_models import InputFormat
from docling.pipeline.simple_pipeline import SimplePipeline
from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
from docling.pipeline.vlm_pipeline import VlmPipeline

from ingest_orquestator_server.config import Settings
from ingest_orquestator_server.infrastructure.docling.docling_format_routes import (
    build_format_options,
    route_metadata_for,
)

EXPECTED_STANDARD_ROUTE_METADATA = {
    "pdf": {
        "input_format": "pdf",
        "selected_pipeline": "standard",
        "format_option": "PdfFormatOption",
        "pipeline_class": "IngestProgressStandardPdfPipeline",
        "backend_class": "ThreadedDoclingParseDocumentBackend",
        "route_kind": "standard",
        "supports_vlm": True,
    },
    "image": {
        "input_format": "image",
        "selected_pipeline": "standard",
        "format_option": "ImageFormatOption",
        "pipeline_class": "IngestProgressStandardPdfPipeline",
        "backend_class": "ImageDocumentBackend",
        "route_kind": "standard",
        "supports_vlm": True,
    },
    "docx": {
        "input_format": "docx",
        "selected_pipeline": "standard",
        "format_option": "WordFormatOption",
        "pipeline_class": "SimplePipeline",
        "backend_class": "MsWordDocumentBackend",
        "route_kind": "simple",
        "supports_vlm": False,
    },
    "pptx": {
        "input_format": "pptx",
        "selected_pipeline": "standard",
        "format_option": "PowerpointFormatOption",
        "pipeline_class": "SimplePipeline",
        "backend_class": "MsPowerpointDocumentBackend",
        "route_kind": "simple",
        "supports_vlm": False,
    },
    "html": {
        "input_format": "html",
        "selected_pipeline": "standard",
        "format_option": "HTMLFormatOption",
        "pipeline_class": "SimplePipeline",
        "backend_class": "HTMLDocumentBackend",
        "route_kind": "simple",
        "supports_vlm": False,
    },
    "md": {
        "input_format": "md",
        "selected_pipeline": "standard",
        "format_option": "MarkdownFormatOption",
        "pipeline_class": "SimplePipeline",
        "backend_class": "MarkdownDocumentBackend",
        "route_kind": "simple",
        "supports_vlm": False,
    },
    "xlsx": {
        "input_format": "xlsx",
        "selected_pipeline": "standard",
        "format_option": "ExcelFormatOption",
        "pipeline_class": "SimplePipeline",
        "backend_class": "MsExcelDocumentBackend",
        "route_kind": "simple",
        "supports_vlm": False,
    },
    "csv": {
        "input_format": "csv",
        "selected_pipeline": "standard",
        "format_option": "CsvFormatOption",
        "pipeline_class": "SimplePipeline",
        "backend_class": "CsvDocumentBackend",
        "route_kind": "simple",
        "supports_vlm": False,
    },
    "json_docling": {
        "input_format": "json_docling",
        "selected_pipeline": "standard",
        "format_option": "FormatOption",
        "pipeline_class": "SimplePipeline",
        "backend_class": "DoclingJSONBackend",
        "route_kind": "simple",
        "supports_vlm": False,
    },
    "asciidoc": {
        "input_format": "asciidoc",
        "selected_pipeline": "standard",
        "format_option": "AsciiDocFormatOption",
        "pipeline_class": "SimplePipeline",
        "backend_class": "AsciiDocBackend",
        "route_kind": "simple",
        "supports_vlm": False,
    },
    "latex": {
        "input_format": "latex",
        "selected_pipeline": "standard",
        "format_option": "LatexFormatOption",
        "pipeline_class": "SimplePipeline",
        "backend_class": "LatexDocumentBackend",
        "route_kind": "simple",
        "supports_vlm": False,
    },
    "vtt": {
        "input_format": "vtt",
        "selected_pipeline": "standard",
        "format_option": "FormatOption",
        "pipeline_class": "SimplePipeline",
        "backend_class": "WebVTTDocumentBackend",
        "route_kind": "simple",
        "supports_vlm": False,
    },
    "xml_jats": {
        "input_format": "xml_jats",
        "selected_pipeline": "standard",
        "format_option": "XMLJatsFormatOption",
        "pipeline_class": "SimplePipeline",
        "backend_class": "JatsDocumentBackend",
        "route_kind": "simple",
        "supports_vlm": False,
    },
    "xml_uspto": {
        "input_format": "xml_uspto",
        "selected_pipeline": "standard",
        "format_option": "PatentUsptoFormatOption",
        "pipeline_class": "SimplePipeline",
        "backend_class": "PatentUsptoDocumentBackend",
        "route_kind": "simple",
        "supports_vlm": False,
    },
    "xml_xbrl": {
        "input_format": "xml_xbrl",
        "selected_pipeline": "standard",
        "format_option": "XBRLFormatOption",
        "pipeline_class": "SimplePipeline",
        "backend_class": "XBRLDocumentBackend",
        "route_kind": "simple",
        "supports_vlm": False,
    },
    "mets_gbs": {
        "input_format": "mets_gbs",
        "selected_pipeline": "standard",
        "format_option": "MetsGbsFormatOption",
        "pipeline_class": "IngestProgressStandardPdfPipeline",
        "backend_class": "MetsGbsDocumentBackend",
        "route_kind": "standard",
        "supports_vlm": False,
    },
    "audio": {
        "input_format": "audio",
        "selected_pipeline": "standard",
        "format_option": "AudioFormatOption",
        "pipeline_class": "AsrPipeline",
        "backend_class": "NoOpBackend",
        "route_kind": "asr",
        "supports_vlm": False,
    },
}

EXPECTED_VLM_ROUTE_METADATA = {
    "pdf": {
        "input_format": "pdf",
        "selected_pipeline": "vlm",
        "format_option": "PdfFormatOption",
        "pipeline_class": "IngestProgressVlmPipeline",
        "backend_class": "DoclingParseDocumentBackend",
        "route_kind": "vlm",
        "supports_vlm": True,
    },
    "image": {
        "input_format": "image",
        "selected_pipeline": "vlm",
        "format_option": "ImageFormatOption",
        "pipeline_class": "IngestProgressVlmPipeline",
        "backend_class": "ImageDocumentBackend",
        "route_kind": "vlm",
        "supports_vlm": True,
    },
}

EXPECTED_ROUTE_STANDARD_METADATA = {
    **EXPECTED_STANDARD_ROUTE_METADATA,
    "mets_gbs": {
        "input_format": "mets_gbs",
        "selected_pipeline": "standard",
        "format_option": "DoclingDefaultFormatOption",
        "pipeline_class": "SimplePipeline",
        "backend_class": "DoclingDefaultBackend",
        "route_kind": "simple",
        "supports_vlm": False,
    },
    "audio": {
        "input_format": "audio",
        "selected_pipeline": "standard",
        "format_option": "DoclingDefaultFormatOption",
        "pipeline_class": "SimplePipeline",
        "backend_class": "DoclingDefaultBackend",
        "route_kind": "simple",
        "supports_vlm": False,
    },
}

ALL_ROUTE_EXTENSIONS = [
    ".pdf",
    ".png",
    ".docx",
    ".pptx",
    ".html",
    ".md",
    ".xlsx",
    ".csv",
    ".json",
    ".adoc",
    ".tex",
    ".vtt",
    ".jats",
    ".uspto",
    ".xbrl",
    ".mets",
    ".mp3",
]


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
    assert format_options[InputFormat.PDF].backend.__name__ == (
        "ThreadedDoclingParseDocumentBackend"
    )
    assert issubclass(format_options[InputFormat.IMAGE].pipeline_cls, StandardPdfPipeline)
    assert issubclass(format_options[InputFormat.MD].pipeline_cls, SimplePipeline)
    assert routes["pdf"].route_kind == "standard"
    assert routes["md"].route_kind == "simple"


def test_build_format_options_routes_all_configurable_formats_without_model_loading() -> None:
    settings = Settings(
        allowed_upload_extensions=ALL_ROUTE_EXTENSIONS,
        docling_pdf_ocr_engine="auto",
    )

    allowed_formats, format_options, routes = build_format_options(
        settings,
        pipeline="standard",
        input_format=None,
    )

    assert {input_format.value for input_format in allowed_formats} == set(
        EXPECTED_STANDARD_ROUTE_METADATA
    )
    assert {input_format.value for input_format in format_options} == set(
        EXPECTED_STANDARD_ROUTE_METADATA
    )
    assert set(routes) == set(EXPECTED_STANDARD_ROUTE_METADATA)
    for input_format, expected_route in EXPECTED_STANDARD_ROUTE_METADATA.items():
        option = format_options[InputFormat(input_format)]

        assert routes[input_format].to_metadata(selected_pipeline="standard") == expected_route
        assert type(option).__name__ == expected_route["format_option"]
        assert option.pipeline_cls.__name__ == expected_route["pipeline_class"]
        assert option.backend.__name__ == expected_route["backend_class"]


def test_build_format_options_routes_selected_vlm_format_only() -> None:
    settings = Settings(
        allowed_upload_extensions=[".docx", ".png", ".pdf"],
        docling_pdf_ocr_engine="auto",
    )

    _allowed_formats, format_options, routes = build_format_options(
        settings,
        pipeline="vlm",
        input_format="pdf",
    )

    assert issubclass(format_options[InputFormat.PDF].pipeline_cls, VlmPipeline)
    assert format_options[InputFormat.PDF].backend.__name__ == "DoclingParseDocumentBackend"
    assert issubclass(format_options[InputFormat.IMAGE].pipeline_cls, StandardPdfPipeline)
    assert issubclass(format_options[InputFormat.DOCX].pipeline_cls, SimplePipeline)
    assert routes["pdf"].route_kind == "vlm"
    assert routes["image"].route_kind == "standard"
    assert routes["docx"].route_kind == "simple"


@pytest.mark.parametrize(
    ("input_format", "expected_route"),
    EXPECTED_ROUTE_STANDARD_METADATA.items(),
)
def test_route_metadata_records_standard_docling_converter_classes(
    input_format: str,
    expected_route: dict[str, object],
) -> None:
    assert route_metadata_for(input_format=input_format, pipeline="standard") == expected_route


@pytest.mark.parametrize(
    ("input_format", "expected_route"),
    EXPECTED_VLM_ROUTE_METADATA.items(),
)
def test_route_metadata_records_vlm_docling_converter_classes(
    input_format: str,
    expected_route: dict[str, object],
) -> None:
    assert route_metadata_for(input_format=input_format, pipeline="vlm") == expected_route


def test_route_metadata_preserves_unknown_format_default() -> None:
    assert route_metadata_for(input_format="unknown", pipeline="standard") == {
        "input_format": "unknown",
        "selected_pipeline": "standard",
        "format_option": "DoclingDefaultFormatOption",
        "pipeline_class": "SimplePipeline",
        "backend_class": "DoclingDefaultBackend",
        "route_kind": "simple",
        "supports_vlm": False,
    }
