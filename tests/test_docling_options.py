import pytest

from ingest_orquestator_server.config import Settings
from ingest_orquestator_server.infrastructure.docling.docling_options import (
    build_pdf_pipeline_options,
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
    assert (
        options.picture_description_options.model_spec.default_repo_id
        == "Qwen/Qwen3-VL-8B-Instruct"
    )
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


def test_default_surya_ocr_engine_requires_external_plugin() -> None:
    from docling.models.factories import get_ocr_factory

    if "suryaocr" in get_ocr_factory(allow_external_plugins=True).registered_kind:
        pytest.skip("SuryaOCR plugin is installed in this environment.")

    with pytest.raises(RuntimeError, match="docling-surya"):
        build_pdf_pipeline_options(Settings())
