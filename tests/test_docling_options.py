import pytest

from ingest_orquestator_server.config import Settings
from ingest_orquestator_server.infrastructure.docling.docling_options import (
    build_pdf_pipeline_options,
    docling_options_metadata,
)


def test_build_pdf_pipeline_options_selects_standard_pipeline_models() -> None:
    options = build_pdf_pipeline_options(Settings(docling_pdf_ocr_engine="auto"))

    assert options.layout_options.model_spec.repo_id == "docling-project/docling-layout-heron-101"
    assert options.ocr_options.kind == "auto"
    assert options.table_structure_options.kind == "docling_tableformer"
    assert options.table_structure_options.mode.value == "accurate"
    assert options.table_structure_options.do_cell_matching is True
    assert options.do_picture_classification is True
    assert (
        options.picture_classification_options.model_spec.repo_id
        == "docling-project/DocumentFigureClassifier-v2.5"
    )
    assert options.do_picture_description is True
    assert str(options.picture_description_options.url) == (
        "http://localhost:8000/v1/chat/completions"
    )
    assert options.picture_description_options.params == {
        "model": "Qwen/Qwen3-VL-8B-Instruct",
        "max_tokens": 2048,
        "temperature": 0.0,
    }
    assert options.do_code_enrichment is False
    assert options.do_formula_enrichment is False


def test_build_pdf_pipeline_options_can_disable_ocr_per_request() -> None:
    options = build_pdf_pipeline_options(
        Settings(docling_pdf_ocr_engine="auto").with_docling_ocr_options(
            do_ocr=False,
            languages=["es"],
        )
    )

    assert options.do_ocr is False


def test_build_pdf_pipeline_options_can_select_remote_picture_description() -> None:
    options = build_pdf_pipeline_options(
        Settings(
            docling_pdf_ocr_engine="auto",
            docling_vlm_model="granite_vision",
            docling_remote_llm_url="http://llm.example/v1/chat/completions",
            parser_worker_count=4,
        )
    )

    assert options.enable_remote_services is True
    assert str(options.picture_description_options.url) == (
        "http://llm.example/v1/chat/completions"
    )
    assert options.picture_description_options.params == {
        "model": "granite_vision",
        "max_tokens": 2048,
        "temperature": 0.0,
    }
    assert options.picture_description_options.concurrency == 4
    assert options.picture_description_options.provenance == "granite_vision (remote_llm)"


def test_build_pdf_pipeline_options_uses_remote_for_custom_picture_model() -> None:
    options = build_pdf_pipeline_options(
        Settings(
            docling_pdf_ocr_engine="auto",
            docling_vlm_model="vendor/custom-vlm",
        )
    )

    assert options.picture_description_options.params["model"] == "vendor/custom-vlm"


def test_build_pdf_pipeline_options_uses_fixed_picture_description_token_limit() -> None:
    options = build_pdf_pipeline_options(Settings(docling_pdf_ocr_engine="auto"))

    assert options.picture_description_options.params["max_tokens"] == 2048


def test_docling_options_metadata_records_runtime_decisions() -> None:
    metadata = docling_options_metadata(
        Settings(
            docling_vlm_model="granite_vision",
        ),
        input_format="pdf",
        pipeline="vlm",
    )

    assert metadata["runtime"]["stages"]["vlm_convert"]["resolved_runtime"] == "remote_llm"
    assert metadata["active_options"]["pipeline_options"]["runtime"] == "remote_llm"
    assert metadata["runtime"]["policy"]["remote_runtime"] == "remote_llm"
    assert metadata["runtime"]["policy"]["backend_vlm_loading"] == "disabled"
    assert (
        metadata["runtime"]["policy"]["remote_llm"]["url"]
        == "http://localhost:8000/v1/chat/completions"
    )
    assert (
        metadata["runtime"]["stages"]["picture_description"]["resolved_runtime"]
        == "remote_llm"
    )
    assert metadata["runtime"]["stages"]["picture_description"]["mode"] == "remote"


def test_default_surya_ocr_engine_requires_external_plugin() -> None:
    from docling.models.factories import get_ocr_factory

    if "suryaocr" in get_ocr_factory(allow_external_plugins=True).registered_kind:
        pytest.skip("SuryaOCR plugin is installed in this environment.")

    with pytest.raises(RuntimeError, match="docling-surya"):
        build_pdf_pipeline_options(Settings())
