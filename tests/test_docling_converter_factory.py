from docling.datamodel.base_models import InputFormat
from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
from docling.pipeline.vlm_pipeline import VlmPipeline

from ingest_orquestator_server.config import Settings
from ingest_orquestator_server.infrastructure.docling.docling_converter_factory import (
    DoclingConverterFactory,
)


def test_converter_factory_allows_configured_formats_without_pdf_options_for_md() -> None:
    converter = DoclingConverterFactory().create(
        Settings(allowed_upload_extensions=[".md", ".pdf"], docling_pdf_ocr_engine="auto"),
        input_format="md",
        pipeline="standard",
    )

    assert converter.allowed_formats == [InputFormat.MD, InputFormat.PDF]
    assert issubclass(
        converter.format_to_options[InputFormat.PDF].pipeline_cls,
        StandardPdfPipeline,
    )


def test_converter_factory_uses_vlm_pipeline_for_pdf() -> None:
    converter = DoclingConverterFactory().create(
        Settings(allowed_upload_extensions=[".pdf"], docling_pdf_ocr_engine="auto"),
        input_format="pdf",
        pipeline="vlm",
    )

    assert issubclass(converter.format_to_options[InputFormat.PDF].pipeline_cls, VlmPipeline)
    vlm_options = converter.format_to_options[InputFormat.PDF].pipeline_options.vlm_options
    assert str(vlm_options.url) == "http://localhost:8000/v1/chat/completions"
    assert vlm_options.params["model"] == "Qwen/Qwen3-VL-8B-Instruct"


def test_converter_factory_uses_remote_llm_options_for_pdf() -> None:
    converter = DoclingConverterFactory().create(
        Settings(
            allowed_upload_extensions=[".pdf"],
            docling_pdf_ocr_engine="auto",
            docling_vlm_model="granite_vision",
            docling_remote_llm_url="http://llm.example/v1/chat/completions",
            parser_worker_count=8,
        ),
        input_format="pdf",
        pipeline="vlm",
    )

    vlm_options = converter.format_to_options[InputFormat.PDF].pipeline_options.vlm_options
    assert str(vlm_options.url) == "http://llm.example/v1/chat/completions"
    assert vlm_options.params == {
        "model": "granite_vision",
        "max_tokens": 4096,
        "temperature": 0.0,
    }
    assert vlm_options.concurrency == 8


def test_converter_factory_passes_remote_llm_tuning_to_api_options() -> None:
    converter = DoclingConverterFactory().create(
        Settings(
            allowed_upload_extensions=[".pdf"],
            docling_pdf_ocr_engine="auto",
            docling_vlm_model="Qwen/Qwen3-VL-8B-Instruct",
            docling_remote_llm_url="http://llm.example/v1/chat/completions",
            docling_remote_llm_model="served-qwen3",
            docling_remote_llm_max_tokens=2048,
            docling_remote_llm_temperature=0.2,
            parser_worker_count=3,
        ),
        input_format="pdf",
        pipeline="vlm",
    )

    vlm_options = converter.format_to_options[InputFormat.PDF].pipeline_options.vlm_options
    assert str(vlm_options.url) == "http://llm.example/v1/chat/completions"
    assert vlm_options.params == {
        "model": "served-qwen3",
        "max_tokens": 2048,
        "temperature": 0.2,
    }
    assert vlm_options.temperature == 0.2
    assert vlm_options.concurrency == 3


def test_converter_factory_uses_vlm_pipeline_for_image() -> None:
    converter = DoclingConverterFactory().create(
        Settings(allowed_upload_extensions=[".png"], docling_pdf_ocr_engine="auto"),
        input_format="image",
        pipeline="vlm",
    )

    assert issubclass(converter.format_to_options[InputFormat.IMAGE].pipeline_cls, VlmPipeline)


def test_converter_factory_uses_standard_options_for_image() -> None:
    converter = DoclingConverterFactory().create(
        Settings(
            allowed_upload_extensions=[".png"],
            docling_allow_external_plugins=True,
            docling_pdf_ocr_engine="auto",
        ),
        input_format="image",
        pipeline="standard",
    )

    image_options = converter.format_to_options[InputFormat.IMAGE]
    assert issubclass(image_options.pipeline_cls, StandardPdfPipeline)
    assert image_options.pipeline_options.allow_external_plugins is True
    assert image_options.pipeline_options.ocr_options.kind == "auto"


def test_converter_factory_uses_configured_xbrl_backend_options() -> None:
    converter = DoclingConverterFactory().create(
        Settings(
            allowed_upload_extensions=[".xbrl"],
            docling_xbrl_enable_local_fetch=True,
            docling_xbrl_enable_remote_fetch=False,
        ),
        input_format="xml_xbrl",
        pipeline="standard",
    )

    xbrl_options = converter.format_to_options[InputFormat.XML_XBRL]
    assert xbrl_options.backend_options.enable_local_fetch is True
    assert xbrl_options.backend_options.enable_remote_fetch is False
    assert xbrl_options.pipeline_options.allow_external_plugins is True
