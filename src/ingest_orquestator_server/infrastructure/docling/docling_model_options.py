from __future__ import annotations

from typing import Any

from ingest_orquestator_server.config.docling_defaults import (
    DOCLING_PICTURE_DESCRIPTION_MODEL,
    DOCLING_TABLE_STRUCTURE_BACKEND_GRANITE_VISION,
)
from ingest_orquestator_server.config.settings import Settings


def build_layout_options(settings: Settings) -> Any:
    from docling.datamodel.layout_model_specs import (
        DOCLING_LAYOUT_EGRET_LARGE,
        DOCLING_LAYOUT_EGRET_MEDIUM,
        DOCLING_LAYOUT_EGRET_XLARGE,
        DOCLING_LAYOUT_HERON,
        DOCLING_LAYOUT_HERON_101,
        DOCLING_LAYOUT_V2,
    )
    from docling.datamodel.pipeline_options import LayoutOptions

    model_specs = {
        "docling-layout-heron": DOCLING_LAYOUT_HERON,
        "docling_layout_heron": DOCLING_LAYOUT_HERON,
        "docling-layout-heron-101": DOCLING_LAYOUT_HERON_101,
        "docling_layout_heron_101": DOCLING_LAYOUT_HERON_101,
        "docling-layout-egret-medium": DOCLING_LAYOUT_EGRET_MEDIUM,
        "docling_layout_egret_medium": DOCLING_LAYOUT_EGRET_MEDIUM,
        "docling-layout-egret-large": DOCLING_LAYOUT_EGRET_LARGE,
        "docling_layout_egret_large": DOCLING_LAYOUT_EGRET_LARGE,
        "docling-layout-egret-xlarge": DOCLING_LAYOUT_EGRET_XLARGE,
        "docling_layout_egret_xlarge": DOCLING_LAYOUT_EGRET_XLARGE,
        "docling-layout-v2": DOCLING_LAYOUT_V2,
        "docling_layout_v2": DOCLING_LAYOUT_V2,
    }
    model_spec = model_specs.get(settings.docling_pdf_layout_model)
    if model_spec is None:
        raise ValueError(
            "Unsupported Docling layout model "
            f"{settings.docling_pdf_layout_model!r}. Supported values: "
            f"{', '.join(sorted(model_specs))}."
        )
    return LayoutOptions(model_spec=model_spec)


def build_ocr_options(settings: Settings) -> Any:
    if not settings.docling_pdf_do_ocr:
        from docling.datamodel.pipeline_options import OcrAutoOptions

        return OcrAutoOptions()

    from docling.models.factories import get_ocr_factory

    factory = get_ocr_factory(allow_external_plugins=settings.docling_allow_external_plugins)
    try:
        ocr_options = factory.create_options(kind=settings.docling_pdf_ocr_engine)
    except Exception as exc:
        raise RuntimeError(
            "Docling OCR engine "
            f"{settings.docling_pdf_ocr_engine!r} is not available. "
            "For the default SuryaOCR engine, install `docling-surya==0.1.0`, "
            "use Python 3.12+ on Linux x86_64, and keep "
            "`INGEST_DOCLING_ALLOW_EXTERNAL_PLUGINS=true`."
        ) from exc

    if settings.docling_pdf_ocr_languages:
        ocr_options.lang = settings.docling_pdf_ocr_languages
    if settings.docling_pdf_ocr_use_gpu is not None and hasattr(ocr_options, "use_gpu"):
        ocr_options.use_gpu = settings.docling_pdf_ocr_use_gpu
    return ocr_options


def build_table_structure_options(settings: Settings) -> Any:
    from docling.datamodel.pipeline_options import (
        GraniteVisionTableStructureOptions,
        TableFormerMode,
        TableStructureOptions,
    )

    if (
        settings.docling_pdf_table_structure_backend
        == DOCLING_TABLE_STRUCTURE_BACKEND_GRANITE_VISION
    ):
        _validate_granite_vision_table_model(settings.docling_pdf_table_structure_vlm_model)
        return GraniteVisionTableStructureOptions()

    return TableStructureOptions(
        do_cell_matching=settings.docling_pdf_table_do_cell_matching,
        mode=TableFormerMode(settings.docling_pdf_table_structure_mode),
    )


def build_picture_classification_options(settings: Settings) -> Any:
    from docling.datamodel.picture_classification_options import (
        DocumentPictureClassifierOptions,
    )

    return DocumentPictureClassifierOptions.from_preset(
        settings.docling_pdf_picture_classifier_preset
    )


def build_picture_description_options(settings: Settings) -> Any:
    from docling.datamodel.pipeline_options import PictureDescriptionVlmEngineOptions

    model_name = settings.docling_pdf_picture_description_model.strip()
    if model_name.lower() in {"qwen", "qwen2.5-vl-3b", "qwen2.5-vl-3b-instruct"}:
        return PictureDescriptionVlmEngineOptions.from_preset("qwen")
    if model_name == DOCLING_PICTURE_DESCRIPTION_MODEL:
        return _build_qwen3_picture_description_options(settings)
    return _build_custom_picture_description_options(settings)


def build_code_formula_options(settings: Settings) -> Any:
    from docling.datamodel.pipeline_options import CodeFormulaVlmOptions

    return CodeFormulaVlmOptions.from_preset(settings.docling_pdf_code_formula_preset)


def _build_qwen3_picture_description_options(settings: Settings) -> Any:
    from docling.datamodel.pipeline_options import PictureDescriptionVlmEngineOptions
    from docling.datamodel.pipeline_options_vlm_model import (
        ResponseFormat,
        TransformersModelType,
    )
    from docling.datamodel.stage_model_specs import EngineModelConfig, VlmModelSpec
    from docling.datamodel.vlm_engine_options import AutoInlineVlmEngineOptions
    from docling.models.inference_engines.vlm.base import VlmEngineType

    return PictureDescriptionVlmEngineOptions(
        engine_options=AutoInlineVlmEngineOptions(),
        model_spec=VlmModelSpec(
            name="Qwen3-VL-8B-Instruct",
            default_repo_id=DOCLING_PICTURE_DESCRIPTION_MODEL,
            prompt=settings.docling_pdf_picture_description_prompt,
            response_format=ResponseFormat.PLAINTEXT,
            supported_engines={VlmEngineType.TRANSFORMERS},
            engine_overrides={
                VlmEngineType.TRANSFORMERS: EngineModelConfig(
                    torch_dtype="bfloat16",
                    extra_config={
                        "transformers_model_type": (
                            TransformersModelType.AUTOMODEL_IMAGETEXTTOTEXT
                        ),
                    },
                ),
            },
        ),
        prompt=settings.docling_pdf_picture_description_prompt,
    )


def _build_custom_picture_description_options(settings: Settings) -> Any:
    from docling.datamodel.pipeline_options import PictureDescriptionVlmEngineOptions
    from docling.datamodel.pipeline_options_vlm_model import (
        ResponseFormat,
        TransformersModelType,
    )
    from docling.datamodel.stage_model_specs import EngineModelConfig, VlmModelSpec
    from docling.datamodel.vlm_engine_options import AutoInlineVlmEngineOptions
    from docling.models.inference_engines.vlm.base import VlmEngineType

    return PictureDescriptionVlmEngineOptions(
        engine_options=AutoInlineVlmEngineOptions(),
        model_spec=VlmModelSpec(
            name=settings.docling_pdf_picture_description_model.rsplit("/", maxsplit=1)[-1],
            default_repo_id=settings.docling_pdf_picture_description_model,
            prompt=settings.docling_pdf_picture_description_prompt,
            response_format=ResponseFormat.PLAINTEXT,
            supported_engines={VlmEngineType.TRANSFORMERS},
            engine_overrides={
                VlmEngineType.TRANSFORMERS: EngineModelConfig(
                    extra_config={
                        "transformers_model_type": (
                            TransformersModelType.AUTOMODEL_IMAGETEXTTOTEXT
                        ),
                    },
                ),
            },
        ),
        prompt=settings.docling_pdf_picture_description_prompt,
    )


def _validate_granite_vision_table_model(model: str) -> None:
    valid_values = {"granite-vision-4.1-4b", "ibm-granite/granite-vision-4.1-4b"}
    if model not in valid_values:
        raise ValueError(
            "Docling standard pipeline currently exposes Granite Vision table structure "
            "through the hard-coded granite-vision-4.1-4b model. Supported values: "
            f"{', '.join(sorted(valid_values))}."
        )
