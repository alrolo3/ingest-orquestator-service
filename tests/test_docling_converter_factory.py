from docling.datamodel.base_models import InputFormat
from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
from docling.pipeline.vlm_pipeline import VlmPipeline

from ingest_orquestator_server.config import Settings
from ingest_orquestator_server.infrastructure.docling.docling_converter_factory import (
    DoclingConverterFactory,
)


def test_converter_factory_allows_configured_formats_without_pdf_options_for_md() -> None:
    converter = DoclingConverterFactory().create(
        Settings(docling_allowed_formats=["md", "pdf"], docling_pdf_ocr_engine="auto"),
        input_format="md",
        pipeline="standard",
    )

    assert converter.allowed_formats == [InputFormat.MD, InputFormat.PDF]
    assert converter.format_to_options[InputFormat.PDF].pipeline_cls == StandardPdfPipeline


def test_converter_factory_uses_vlm_pipeline_for_pdf() -> None:
    converter = DoclingConverterFactory().create(
        Settings(docling_allowed_formats=["pdf"], docling_pdf_ocr_engine="auto"),
        input_format="pdf",
        pipeline="vlm",
    )

    assert converter.format_to_options[InputFormat.PDF].pipeline_cls == VlmPipeline
    assert (
        converter.format_to_options[InputFormat.PDF].pipeline_options.vlm_options.repo_id
        == "Qwen/Qwen3-VL-8B-Instruct"
    )


def test_converter_factory_uses_vlm_pipeline_for_image() -> None:
    converter = DoclingConverterFactory().create(
        Settings(docling_allowed_formats=["image"], docling_pdf_ocr_engine="auto"),
        input_format="image",
        pipeline="vlm",
    )

    assert converter.format_to_options[InputFormat.IMAGE].pipeline_cls == VlmPipeline
