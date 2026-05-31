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
    assert options.picture_description_options.kind == "vlm"
    assert options.picture_description_options.repo_id == "Qwen/Qwen3-VL-8B-Instruct"
    assert options.picture_description_options.generation_config == {
        "max_new_tokens": 1024,
        "do_sample": False,
    }
    assert options.do_code_enrichment is True
    assert options.do_formula_enrichment is True
    assert (
        options.code_formula_options.model_spec.default_repo_id == "docling-project/CodeFormulaV2"
    )


def test_build_pdf_pipeline_options_can_select_granite_vision_table_structure() -> None:
    options = build_pdf_pipeline_options(
        Settings(
            docling_pdf_ocr_engine="auto",
            docling_pdf_table_structure_backend="granite_vision",
        )
    )

    assert options.table_structure_options.kind == "granite_vision_table"


def test_build_pdf_pipeline_options_can_select_remote_picture_description() -> None:
    options = build_pdf_pipeline_options(
        Settings(
            docling_pdf_ocr_engine="auto",
            docling_pdf_picture_description_model="granite_vision",
            docling_pdf_picture_description_runtime="remote_llm",
            docling_remote_llm_url="http://llm.example/v1/chat/completions",
            docling_remote_llm_concurrency=4,
        )
    )

    assert options.enable_remote_services is True
    assert str(options.picture_description_options.url) == (
        "http://llm.example/v1/chat/completions"
    )
    assert options.picture_description_options.params == {
        "model": "granite_vision",
        "max_tokens": 1024,
        "temperature": 0.0,
    }
    assert options.picture_description_options.concurrency == 4
    assert options.picture_description_options.provenance == "granite_vision (remote_llm)"


def test_build_pdf_pipeline_options_passes_remote_code_to_custom_picture_model() -> None:
    options = build_pdf_pipeline_options(
        Settings(
            docling_pdf_ocr_engine="auto",
            docling_pdf_picture_description_model="vendor/custom-vlm",
            docling_pdf_picture_description_runtime="transformers",
            docling_vlm_trust_remote_code=True,
        )
    )

    assert options.picture_description_options.model_spec.default_repo_id == ("vendor/custom-vlm")
    assert options.picture_description_options.model_spec.trust_remote_code is True
    assert options.picture_description_options.model_spec.max_new_tokens == 1024
    assert options.picture_description_options.generation_config["max_new_tokens"] == 1024


def test_build_pdf_pipeline_options_allows_picture_description_token_limit() -> None:
    options = build_pdf_pipeline_options(
        Settings(
            docling_pdf_ocr_engine="auto",
            docling_pdf_picture_description_max_new_tokens=1536,
        )
    )

    assert options.picture_description_options.generation_config == {
        "max_new_tokens": 1536,
        "do_sample": False,
    }


def test_docling_options_metadata_records_runtime_decisions() -> None:
    metadata = docling_options_metadata(
        Settings(
            docling_vlm_model="granite_vision",
            docling_vlm_runtime="remote_llm",
            docling_vlm_trust_remote_code=True,
            docling_pdf_picture_description_model="Qwen/Qwen3-VL-8B-Instruct",
            docling_pdf_picture_description_runtime="remote_llm",
        ),
        input_format="pdf",
        pipeline="vlm",
    )

    assert metadata["runtime"]["stages"]["vlm_convert"]["resolved_runtime"] == "remote_llm"
    assert metadata["active_options"]["pipeline_options"]["trust_remote_code"] is True
    assert metadata["runtime"]["policy"]["remote_runtime"] == "remote_llm"
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
