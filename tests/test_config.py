import pytest
from pydantic import ValidationError

from ingest_orquestator_server.config import Settings


def test_settings_accept_cuda_device() -> None:
    settings = Settings(docling_accelerator_device="CUDA:1")

    assert settings.docling_accelerator_device == "cuda:1"


def test_settings_reject_unknown_accelerator_device() -> None:
    with pytest.raises(ValidationError):
        Settings(docling_accelerator_device="gpu")


def test_settings_parse_allowed_upload_extensions_from_string() -> None:
    settings = Settings(allowed_upload_extensions=".PDF, md, .txt")

    assert settings.allowed_upload_extensions == [".md", ".pdf", ".txt"]


def test_env_example_loads() -> None:
    settings = Settings(_env_file=".env.example")

    assert settings.docling_pdf_ocr_engine == "suryaocr"
    assert settings.docling_pdf_ocr_languages == ["en"]


def test_cuda_gpu_env_loads() -> None:
    settings = Settings(_env_file="env-cuda-gpu")

    assert settings.docling_accelerator_device == "cuda"
    assert settings.docling_num_threads == 32
    assert settings.docling_cuda_use_flash_attention2 is False
    assert settings.docling_pdf_ocr_use_gpu is True
    assert settings.docling_pdf_ocr_batch_size == 32
    assert settings.docling_pdf_layout_batch_size == 32
    assert settings.docling_pdf_table_batch_size == 32
    assert settings.docling_pdf_queue_max_size == 512


def test_cpu_env_loads() -> None:
    settings = Settings(_env_file="env-cpu")

    assert settings.docling_accelerator_device == "cpu"
    assert settings.docling_pdf_ocr_engine == "auto"
    assert settings.docling_pdf_ocr_use_gpu is False
    assert settings.docling_pdf_do_picture_classification is False
    assert settings.docling_pdf_do_picture_description is False
    assert settings.docling_pdf_do_code_enrichment is False
    assert settings.docling_pdf_do_formula_enrichment is False
    assert settings.docling_pdf_ocr_batch_size == 1
    assert settings.docling_pdf_queue_max_size == 32


def test_settings_use_requested_docling_standard_pipeline_defaults() -> None:
    settings = Settings()

    assert settings.docling_allow_external_plugins is True
    assert settings.docling_pdf_layout_model == "docling-layout-heron-101"
    assert settings.docling_pdf_ocr_engine == "suryaocr"
    assert settings.docling_pdf_ocr_languages == ["en"]
    assert settings.docling_pdf_table_structure_backend == "tableformer"
    assert settings.docling_pdf_table_structure_mode == "accurate"
    assert settings.docling_pdf_table_do_cell_matching is True
    assert settings.docling_pdf_table_structure_vlm_model == "granite-vision-4.1-4b"
    assert settings.docling_pdf_do_picture_classification is True
    assert settings.docling_pdf_picture_classifier_preset == "document_figure_classifier_v2"
    assert settings.docling_pdf_do_picture_description is True
    assert settings.docling_pdf_picture_description_model == "Qwen/Qwen3-VL-8B-Instruct"
    assert settings.docling_pdf_do_code_enrichment is True
    assert settings.docling_pdf_do_formula_enrichment is True
    assert settings.docling_pdf_code_formula_preset == "codeformulav2"


def test_settings_parse_docling_ocr_languages_from_string() -> None:
    settings = Settings(docling_pdf_ocr_languages="en,es")

    assert settings.docling_pdf_ocr_languages == ["en", "es"]


def test_settings_parse_docling_allowed_formats_from_string() -> None:
    settings = Settings(docling_allowed_formats="pdf, image, docx")

    assert settings.docling_allowed_formats == ["docx", "image", "pdf"]


def test_settings_reject_unknown_docling_format() -> None:
    with pytest.raises(ValidationError):
        Settings(docling_allowed_formats=["pdf", "unknown"])


def test_settings_grouped_config_views() -> None:
    settings = Settings(docling_pipeline="vlm", docling_vlm_runtime="transformers")

    assert settings.docling_common_config.pipeline == "vlm"
    assert settings.docling_vlm_config.runtime == "transformers"
    assert settings.chunking_config.embedding_output_enabled is True


def test_settings_reject_unknown_table_structure_backend() -> None:
    with pytest.raises(ValidationError):
        Settings(docling_pdf_table_structure_backend="unknown")
