from __future__ import annotations

import re
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from ingest_orquestator_server.config.docling_defaults import (
    DOCLING_PICTURE_DESCRIPTION_MODEL,
    DOCLING_TABLE_STRUCTURE_BACKEND_GRANITE_VISION,
)
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.docling.docling_runtime_capabilities import (
    RUNTIME_AUTO_INLINE,
    RUNTIME_TRANSFORMERS,
    RUNTIME_VLLM,
    RuntimeResolution,
    resolve_picture_description_runtime,
    resolve_vlm_convert_runtime,
)
from ingest_orquestator_server.infrastructure.docling.ocr_engine_registry import (
    OcrEngineRegistry,
)


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

    registry = OcrEngineRegistry(allow_external_plugins=settings.docling_allow_external_plugins)
    try:
        ocr_options = registry.create_options(kind=settings.docling_pdf_ocr_engine)
    except Exception as exc:
        raise RuntimeError(
            "Docling OCR engine "
            f"{settings.docling_pdf_ocr_engine!r} is not available. "
            "For the default SuryaOCR engine, install `docling-surya==0.1.0`, "
            "use Python 3.12+ on Linux x86_64, keep "
            "`INGEST_DOCLING_ALLOW_EXTERNAL_PLUGINS=true`, and pin "
            "`transformers>=4.57,<5`. "
            f"Available engines: {', '.join(registry.available_engines()) or '<none>'}."
        ) from exc

    _validate_surya_transformers_compatibility(settings)

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
    resolution = resolve_picture_description_runtime(settings)
    engine_options = build_vlm_engine_options(resolution, settings)
    generation_config = _picture_description_generation_config(settings)
    if resolution.preset is not None:
        return PictureDescriptionVlmEngineOptions.from_preset(
            resolution.preset,
            engine_options=engine_options,
            prompt=settings.docling_pdf_picture_description_prompt,
            generation_config=generation_config,
        )
    if (
        model_name == DOCLING_PICTURE_DESCRIPTION_MODEL
        and resolution.resolved_runtime == RUNTIME_TRANSFORMERS
    ):
        return _build_qwen3_transformers_picture_description_options(settings)
    if model_name == DOCLING_PICTURE_DESCRIPTION_MODEL:
        return _build_qwen3_picture_description_options(settings, resolution)
    return _build_custom_picture_description_options(settings, resolution)


def build_code_formula_options(settings: Settings) -> Any:
    from docling.datamodel.pipeline_options import CodeFormulaVlmOptions

    return CodeFormulaVlmOptions.from_preset(settings.docling_pdf_code_formula_preset)


def build_vlm_convert_options(settings: Settings) -> Any:
    from docling.datamodel.pipeline_options import VlmConvertOptions
    from docling.datamodel.pipeline_options_vlm_model import (
        InferenceFramework,
        InlineVlmOptions,
        ResponseFormat,
        TransformersModelType,
    )

    resolution = resolve_vlm_convert_runtime(settings)
    trust_remote_code = settings.effective_docling_vlm_trust_remote_code
    if resolution.preset is not None:
        return VlmConvertOptions.from_preset(
            resolution.preset,
            engine_options=build_vlm_engine_options(resolution, settings),
            scale=settings.docling_vlm_scale,
        )

    return InlineVlmOptions(
        prompt=settings.docling_vlm_prompt,
        repo_id=settings.docling_vlm_model,
        inference_framework=InferenceFramework(
            RUNTIME_VLLM if resolution.resolved_runtime == RUNTIME_VLLM else RUNTIME_TRANSFORMERS
        ),
        transformers_model_type=TransformersModelType.AUTOMODEL_IMAGETEXTTOTEXT,
        response_format=ResponseFormat(settings.docling_vlm_response_format),
        torch_dtype=settings.docling_vlm_torch_dtype,
        load_in_8bit=settings.docling_vlm_load_in_8bit,
        trust_remote_code=trust_remote_code,
        scale=settings.docling_vlm_scale,
        max_new_tokens=settings.docling_vlm_max_new_tokens,
        extra_generation_config=_inline_vllm_extra_generation_config(settings, resolution),
    )


def build_vlm_engine_options(resolution: RuntimeResolution, settings: Settings) -> Any:
    from docling.datamodel.vlm_engine_options import (
        AutoInlineVlmEngineOptions,
        TransformersVlmEngineOptions,
        VllmCudaGraphMode,
        VllmVlmEngineOptions,
    )

    if resolution.resolved_runtime == RUNTIME_VLLM:
        return VllmVlmEngineOptions(
            tensor_parallel_size=settings.docling_vllm_tensor_parallel_size,
            gpu_memory_utilization=settings.docling_vllm_gpu_memory_utilization,
            trust_remote_code=settings.effective_docling_vlm_trust_remote_code,
            cudagraph_mode=VllmCudaGraphMode(settings.docling_vllm_cudagraph_mode),
            model_impl=settings.docling_vllm_model_impl,
        )
    if resolution.resolved_runtime == RUNTIME_AUTO_INLINE:
        return AutoInlineVlmEngineOptions(prefer_vllm=resolution.vllm_supported)
    return TransformersVlmEngineOptions(
        torch_dtype=settings.docling_vlm_torch_dtype,
        load_in_8bit=settings.docling_vlm_load_in_8bit,
        trust_remote_code=settings.effective_docling_vlm_trust_remote_code,
    )


def _inline_vllm_extra_generation_config(
    settings: Settings,
    resolution: RuntimeResolution,
) -> dict[str, Any]:
    if resolution.resolved_runtime != RUNTIME_VLLM:
        return {}

    extra_config: dict[str, Any] = {
        "gpu_memory_utilization": settings.docling_vllm_gpu_memory_utilization,
        "tensor_parallel_size": settings.docling_vllm_tensor_parallel_size,
    }
    if settings.docling_vlm_torch_dtype:
        extra_config["dtype"] = settings.docling_vlm_torch_dtype
    if settings.docling_vllm_max_model_len is not None:
        extra_config["max_model_len"] = settings.docling_vllm_max_model_len
    if settings.docling_vllm_max_num_batched_tokens is not None:
        extra_config["max_num_batched_tokens"] = settings.docling_vllm_max_num_batched_tokens
    if settings.docling_vllm_enforce_eager is not None:
        extra_config["enforce_eager"] = settings.docling_vllm_enforce_eager
    elif settings.docling_vllm_cudagraph_mode == "NONE":
        extra_config["enforce_eager"] = True

    return extra_config


def _build_qwen3_picture_description_options(
    settings: Settings,
    resolution: RuntimeResolution,
) -> Any:
    from docling.datamodel.pipeline_options import PictureDescriptionVlmEngineOptions
    from docling.datamodel.pipeline_options_vlm_model import (
        ResponseFormat,
        TransformersModelType,
    )
    from docling.datamodel.stage_model_specs import EngineModelConfig, VlmModelSpec
    from docling.models.inference_engines.vlm.base import VlmEngineType

    return PictureDescriptionVlmEngineOptions(
        engine_options=build_vlm_engine_options(resolution, settings),
        model_spec=VlmModelSpec(
            name="Qwen3-VL-8B-Instruct",
            default_repo_id=DOCLING_PICTURE_DESCRIPTION_MODEL,
            prompt=settings.docling_pdf_picture_description_prompt,
            response_format=ResponseFormat.PLAINTEXT,
            trust_remote_code=settings.effective_docling_vlm_trust_remote_code,
            max_new_tokens=settings.docling_pdf_picture_description_max_new_tokens,
            supported_engines=_supported_picture_description_engines(resolution),
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
        generation_config=_picture_description_generation_config(settings),
    )


def _build_qwen3_transformers_picture_description_options(settings: Settings) -> Any:
    from docling.datamodel.pipeline_options import PictureDescriptionVlmOptions

    return PictureDescriptionVlmOptions(
        repo_id=DOCLING_PICTURE_DESCRIPTION_MODEL,
        prompt=settings.docling_pdf_picture_description_prompt,
        generation_config=_picture_description_generation_config(settings),
    )


def _build_custom_picture_description_options(
    settings: Settings,
    resolution: RuntimeResolution,
) -> Any:
    from docling.datamodel.pipeline_options import PictureDescriptionVlmEngineOptions
    from docling.datamodel.pipeline_options_vlm_model import (
        ResponseFormat,
        TransformersModelType,
    )
    from docling.datamodel.stage_model_specs import EngineModelConfig, VlmModelSpec
    from docling.models.inference_engines.vlm.base import VlmEngineType

    return PictureDescriptionVlmEngineOptions(
        engine_options=build_vlm_engine_options(resolution, settings),
        model_spec=VlmModelSpec(
            name=settings.docling_pdf_picture_description_model.rsplit("/", maxsplit=1)[-1],
            default_repo_id=settings.docling_pdf_picture_description_model,
            prompt=settings.docling_pdf_picture_description_prompt,
            response_format=ResponseFormat.PLAINTEXT,
            trust_remote_code=settings.effective_docling_vlm_trust_remote_code,
            max_new_tokens=settings.docling_pdf_picture_description_max_new_tokens,
            supported_engines=_supported_picture_description_engines(resolution),
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
        generation_config=_picture_description_generation_config(settings),
    )


def _picture_description_generation_config(settings: Settings) -> dict[str, Any]:
    return {
        "max_new_tokens": settings.docling_pdf_picture_description_max_new_tokens,
        "do_sample": False,
    }


def _supported_picture_description_engines(resolution: RuntimeResolution) -> set[Any]:
    from docling.models.inference_engines.vlm.base import VlmEngineType

    engines = {VlmEngineType.TRANSFORMERS}
    if resolution.resolved_runtime == RUNTIME_VLLM or resolution.allow_unverified_vllm_model:
        engines.add(VlmEngineType.VLLM)
    return engines


def _validate_granite_vision_table_model(model: str) -> None:
    valid_values = {"granite-vision-4.1-4b", "ibm-granite/granite-vision-4.1-4b"}
    if model not in valid_values:
        raise ValueError(
            "Docling standard pipeline currently exposes Granite Vision table structure "
            "through the hard-coded granite-vision-4.1-4b model. Supported values: "
            f"{', '.join(sorted(valid_values))}."
        )


def _validate_surya_transformers_compatibility(settings: Settings) -> None:
    if settings.docling_pdf_ocr_engine != "suryaocr":
        return

    transformers_version = _get_installed_distribution_version("transformers")
    if transformers_version is None:
        return

    major_version = _parse_major_version(transformers_version)
    if major_version is not None and major_version >= 5:
        raise RuntimeError(
            "SuryaOCR is not compatible with the installed Transformers version "
            f"{transformers_version}. Install the project pin with "
            '`python -m pip install --upgrade --force-reinstall "transformers>=4.57,<5"` '
            "and then rerun `python -m pip install -r requirements.txt`."
        )


def _get_installed_distribution_version(distribution_name: str) -> str | None:
    try:
        return version(distribution_name)
    except PackageNotFoundError:
        return None


def _parse_major_version(version_string: str) -> int | None:
    match = re.match(r"^(\d+)", version_string)
    if match is None:
        return None
    return int(match.group(1))
