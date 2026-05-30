from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from ingest_orquestator_server.config.settings import Settings

RUNTIME_AUTO = "auto"
RUNTIME_AUTO_INLINE = "auto_inline"
RUNTIME_TRANSFORMERS = "transformers"
RUNTIME_VLLM = "vllm"

VLM_CONVERT_STAGE = "vlm_convert"
PICTURE_DESCRIPTION_STAGE = "picture_description"

VLM_CONVERT_PRESETS: dict[str, dict[str, Any]] = {
    "granite_docling": {
        "model": "Granite-Docling-258M",
        "repo_id": "ibm-granite/granite-docling-258M",
        "vllm_supported": False,
        "response_format": "doctags",
    },
    "smoldocling": {
        "model": "SmolDocling-256M",
        "repo_id": "docling-project/SmolDocling-256M-preview",
        "vllm_supported": False,
        "response_format": "doctags",
    },
    "deepseek_ocr": {
        "model": "DeepSeek-OCR-3B",
        "repo_id": "deepseek-ai/DeepSeek-OCR",
        "vllm_supported": False,
        "response_format": "markdown",
    },
    "granite_vision": {
        "model": "Granite-Vision-3.3-2B",
        "repo_id": "ibm-granite/granite-vision-3.3-2b",
        "vllm_supported": True,
        "response_format": "markdown",
    },
    "pixtral": {
        "model": "Pixtral-12B",
        "repo_id": "mistral-community/pixtral-12b",
        "vllm_supported": False,
        "response_format": "markdown",
    },
    "got_ocr": {
        "model": "GOT-OCR-2.0",
        "repo_id": "stepfun-ai/GOT-OCR-2.0-hf",
        "vllm_supported": False,
        "response_format": "markdown",
    },
    "phi4": {
        "model": "Phi-4-Multimodal",
        "repo_id": "microsoft/Phi-4-multimodal-instruct",
        "vllm_supported": True,
        "response_format": "markdown",
    },
    "qwen": {
        "model": "Qwen2.5-VL-3B-Instruct",
        "repo_id": "Qwen/Qwen2.5-VL-3B-Instruct",
        "vllm_supported": False,
        "response_format": "markdown",
    },
    "nanonets_ocr2": {
        "model": "Nanonets-OCR2-3B",
        "repo_id": "nanonets/Nanonets-OCR2-3B",
        "vllm_supported": True,
        "response_format": "markdown",
    },
    "gemma_12b": {
        "model": "Gemma-3-12B",
        "repo_id": "google/gemma-3-12b-it",
        "vllm_supported": False,
        "response_format": "markdown",
    },
    "gemma_27b": {
        "model": "Gemma-3-27B",
        "repo_id": "google/gemma-3-27b-it",
        "vllm_supported": False,
        "response_format": "markdown",
    },
    "dolphin": {
        "model": "Dolphin",
        "repo_id": "ByteDance/Dolphin",
        "vllm_supported": False,
        "response_format": "markdown",
    },
}

PICTURE_DESCRIPTION_PRESETS: dict[str, dict[str, Any]] = {
    "smolvlm": {
        "model": "SmolVLM-256M",
        "repo_id": "HuggingFaceTB/SmolVLM-256M-Instruct",
        "vllm_supported": False,
        "response_format": "plaintext",
    },
    "granite_vision": {
        "model": "Granite-Vision-3.3-2B",
        "repo_id": "ibm-granite/granite-vision-3.3-2b",
        "vllm_supported": True,
        "response_format": "plaintext",
    },
    "pixtral": {
        "model": "Pixtral-12B",
        "repo_id": "mistral-community/pixtral-12b",
        "vllm_supported": False,
        "response_format": "plaintext",
    },
    "qwen": {
        "model": "Qwen2.5-VL-3B-Instruct",
        "repo_id": "Qwen/Qwen2.5-VL-3B-Instruct",
        "vllm_supported": False,
        "response_format": "plaintext",
    },
}

NON_VLLM_STAGE_RUNTIMES: dict[str, dict[str, Any]] = {
    "layout": {
        "model": "docling-layout-heron-101",
        "runtime": "docling-ibm-models",
        "reason": "Layout detection is an object-detection stage, not a VLM stage.",
    },
    "ocr": {
        "model": "suryaocr",
        "runtime": "ocr-engine-specific",
        "reason": "OCR engines use their own runtimes and are not served by vLLM.",
    },
    "table_structure": {
        "model": "TableFormer",
        "runtime": "docling-ibm-models",
        "reason": "TableFormer is a table-structure model, not a VLM stage.",
    },
    "picture_classifier": {
        "model": "DocumentFigureClassifier-v2.5",
        "runtime": "transformers-image-classification",
        "reason": "Picture classification uses a ViT classifier, not a generative VLM.",
    },
    "code_formula": {
        "model": "CodeFormulaV2",
        "runtime": "transformers",
        "reason": "Docling catalog lists CodeFormulaV2 with Transformers/MLX only.",
    },
}


def _aliases(presets: dict[str, dict[str, Any]]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for preset, metadata in presets.items():
        aliases[preset] = preset
        aliases[preset.replace("_", "-")] = preset
        aliases[_normalize_model_key(str(metadata["repo_id"]))] = preset
        aliases[_normalize_model_key(str(metadata["model"]))] = preset
    return aliases


def _normalize_model_key(model: str) -> str:
    return model.strip().lower()


_VLM_CONVERT_ALIASES = _aliases(VLM_CONVERT_PRESETS) | {
    "granite-vision-3.3-2b": "granite_vision",
    "phi-4-multimodal": "phi4",
    "phi-4-multimodal-instruct": "phi4",
    "qwen2.5-vl-3b": "qwen",
    "qwen2.5-vl-3b-instruct": "qwen",
    "nanonets-ocr2-3b": "nanonets_ocr2",
}

_PICTURE_DESCRIPTION_ALIASES = _aliases(PICTURE_DESCRIPTION_PRESETS) | {
    "granite-vision-3.3-2b": "granite_vision",
    "qwen2.5-vl-3b": "qwen",
    "qwen2.5-vl-3b-instruct": "qwen",
    "smolvlm-256m": "smolvlm",
    "smolvlm-256m-instruct": "smolvlm",
}


@dataclass(frozen=True)
class RuntimeResolution:
    stage: str
    model: str
    preset: str | None
    requested_runtime: str
    resolved_runtime: str
    vllm_supported: bool
    fallback_runtime: str | None = None
    fallback_reason: str | None = None
    response_format: str | None = None
    mode: str = "inline"
    allow_unverified_vllm_model: bool = False

    def to_metadata(self) -> dict[str, Any]:
        return asdict(self)


def resolve_vlm_convert_runtime(settings: Settings) -> RuntimeResolution:
    return _resolve_runtime(
        stage=VLM_CONVERT_STAGE,
        model=settings.docling_vlm_model,
        requested_runtime=settings.docling_vlm_runtime,
        fallback_runtime=settings.docling_vllm_fallback_runtime,
        fallback_on_unsupported=settings.docling_vllm_fallback_on_unsupported,
        allow_unverified_vllm_model=settings.docling_vllm_allow_unverified_models,
        aliases=_VLM_CONVERT_ALIASES,
        presets=VLM_CONVERT_PRESETS,
        response_format=settings.docling_vlm_response_format,
    )


def resolve_picture_description_runtime(settings: Settings) -> RuntimeResolution:
    return _resolve_runtime(
        stage=PICTURE_DESCRIPTION_STAGE,
        model=settings.docling_pdf_picture_description_model,
        requested_runtime=settings.docling_pdf_picture_description_runtime,
        fallback_runtime=settings.docling_vllm_fallback_runtime,
        fallback_on_unsupported=settings.docling_vllm_fallback_on_unsupported,
        allow_unverified_vllm_model=settings.docling_vllm_allow_unverified_models,
        aliases=_PICTURE_DESCRIPTION_ALIASES,
        presets=PICTURE_DESCRIPTION_PRESETS,
        response_format="plaintext",
    )


def docling_runtime_metadata(
    settings: Settings,
    *,
    pipeline: str,
) -> dict[str, Any]:
    vlm_resolution = resolve_vlm_convert_runtime(settings)
    picture_resolution = resolve_picture_description_runtime(settings)
    return {
        "policy": {
            "fallback_on_unsupported": settings.docling_vllm_fallback_on_unsupported,
            "fallback_runtime": settings.docling_vllm_fallback_runtime,
            "allow_unverified_vllm_models": settings.docling_vllm_allow_unverified_models,
            "vllm": {
                "tensor_parallel_size": settings.docling_vllm_tensor_parallel_size,
                "gpu_memory_utilization": settings.docling_vllm_gpu_memory_utilization,
                "trust_remote_code": settings.docling_vllm_trust_remote_code,
                "cudagraph_mode": settings.docling_vllm_cudagraph_mode,
                "model_impl": settings.docling_vllm_model_impl,
            },
        },
        "active_pipeline_stage": (vlm_resolution.to_metadata() if pipeline == "vlm" else None),
        "stages": {
            VLM_CONVERT_STAGE: vlm_resolution.to_metadata(),
            PICTURE_DESCRIPTION_STAGE: picture_resolution.to_metadata(),
            "layout": NON_VLLM_STAGE_RUNTIMES["layout"]
            | {"model": settings.docling_pdf_layout_model},
            "ocr": NON_VLLM_STAGE_RUNTIMES["ocr"] | {"model": settings.docling_pdf_ocr_engine},
            "table_structure": _table_structure_metadata(settings),
            "picture_classifier": NON_VLLM_STAGE_RUNTIMES["picture_classifier"]
            | {"model": settings.docling_pdf_picture_classifier_preset},
            "code_formula": NON_VLLM_STAGE_RUNTIMES["code_formula"]
            | {"model": settings.docling_pdf_code_formula_preset},
        },
    }


def _resolve_runtime(
    *,
    stage: str,
    model: str,
    requested_runtime: str,
    fallback_runtime: str,
    fallback_on_unsupported: bool,
    allow_unverified_vllm_model: bool,
    aliases: dict[str, str],
    presets: dict[str, dict[str, Any]],
    response_format: str,
) -> RuntimeResolution:
    normalized_runtime = requested_runtime.strip().lower()
    normalized_model = _normalize_model_key(model)
    preset = aliases.get(normalized_model)
    preset_metadata = presets.get(preset or "")
    vllm_supported = bool(preset_metadata and preset_metadata["vllm_supported"])
    if preset is None and allow_unverified_vllm_model:
        vllm_supported = True

    if normalized_runtime == RUNTIME_AUTO:
        resolved_runtime = RUNTIME_VLLM if vllm_supported else fallback_runtime
    elif normalized_runtime == RUNTIME_AUTO_INLINE:
        resolved_runtime = RUNTIME_AUTO_INLINE
    elif normalized_runtime == RUNTIME_VLLM and not vllm_supported:
        if not fallback_on_unsupported:
            raise ValueError(
                f"Docling {stage} model {model!r} is not documented as vLLM-capable. "
                "Choose a vLLM-supported preset or enable "
                "`INGEST_DOCLING_VLLM_ALLOW_UNVERIFIED_MODELS=true`."
            )
        resolved_runtime = fallback_runtime
    else:
        resolved_runtime = normalized_runtime

    fallback_reason = None
    effective_fallback_runtime = None
    if normalized_runtime == RUNTIME_VLLM and resolved_runtime != RUNTIME_VLLM:
        effective_fallback_runtime = resolved_runtime
        fallback_reason = (
            f"Docling model catalog does not list {model!r} as vLLM-capable for {stage}."
        )
    if normalized_runtime == RUNTIME_AUTO and resolved_runtime != RUNTIME_VLLM:
        effective_fallback_runtime = resolved_runtime
        fallback_reason = (
            f"Automatic runtime resolved to {resolved_runtime!r} because {model!r} "
            f"is not documented as vLLM-capable for {stage}."
        )

    return RuntimeResolution(
        stage=stage,
        model=model,
        preset=preset,
        requested_runtime=normalized_runtime,
        resolved_runtime=resolved_runtime,
        vllm_supported=vllm_supported,
        fallback_runtime=effective_fallback_runtime,
        fallback_reason=fallback_reason,
        response_format=(
            str(preset_metadata.get("response_format"))
            if preset_metadata is not None
            else response_format
        ),
        allow_unverified_vllm_model=allow_unverified_vllm_model,
    )


def _table_structure_metadata(settings: Settings) -> dict[str, Any]:
    if settings.docling_pdf_table_structure_backend == "granite_vision":
        return {
            "model": settings.docling_pdf_table_structure_vlm_model,
            "runtime": "transformers",
            "vllm_supported": False,
            "reason": (
                "Docling catalog currently lists Granite Vision table structure "
                "with Transformers, not vLLM."
            ),
        }
    return NON_VLLM_STAGE_RUNTIMES["table_structure"] | {
        "model": settings.docling_pdf_table_structure_backend,
    }
