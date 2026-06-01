from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from ingest_orquestator_server.config.settings import Settings

RUNTIME_AUTO = "auto"
RUNTIME_AUTO_INLINE = "auto_inline"
RUNTIME_REMOTE_LLM = "remote_llm"
RUNTIME_TRANSFORMERS = "transformers"

VLM_CONVERT_STAGE = "vlm_convert"
PICTURE_DESCRIPTION_STAGE = "picture_description"

VLM_CONVERT_PRESETS: dict[str, dict[str, Any]] = {
    "granite_docling": {
        "model": "Granite-Docling-258M",
        "repo_id": "ibm-granite/granite-docling-258M",
        "response_format": "doctags",
    },
    "smoldocling": {
        "model": "SmolDocling-256M",
        "repo_id": "docling-project/SmolDocling-256M-preview",
        "response_format": "doctags",
    },
    "deepseek_ocr": {
        "model": "DeepSeek-OCR-3B",
        "repo_id": "deepseek-ai/DeepSeek-OCR",
        "response_format": "markdown",
    },
    "granite_vision": {
        "model": "Granite-Vision-3.3-2B",
        "repo_id": "ibm-granite/granite-vision-3.3-2b",
        "response_format": "markdown",
    },
    "pixtral": {
        "model": "Pixtral-12B",
        "repo_id": "mistral-community/pixtral-12b",
        "response_format": "markdown",
    },
    "got_ocr": {
        "model": "GOT-OCR-2.0",
        "repo_id": "stepfun-ai/GOT-OCR-2.0-hf",
        "response_format": "markdown",
    },
    "phi4": {
        "model": "Phi-4-Multimodal",
        "repo_id": "microsoft/Phi-4-multimodal-instruct",
        "response_format": "markdown",
    },
    "qwen": {
        "model": "Qwen2.5-VL-3B-Instruct",
        "repo_id": "Qwen/Qwen2.5-VL-3B-Instruct",
        "response_format": "markdown",
    },
    "nanonets_ocr2": {
        "model": "Nanonets-OCR2-3B",
        "repo_id": "nanonets/Nanonets-OCR2-3B",
        "response_format": "markdown",
    },
    "gemma_12b": {
        "model": "Gemma-3-12B",
        "repo_id": "google/gemma-3-12b-it",
        "response_format": "markdown",
    },
    "gemma_27b": {
        "model": "Gemma-3-27B",
        "repo_id": "google/gemma-3-27b-it",
        "response_format": "markdown",
    },
    "dolphin": {
        "model": "Dolphin",
        "repo_id": "ByteDance/Dolphin",
        "response_format": "markdown",
    },
}

PICTURE_DESCRIPTION_PRESETS: dict[str, dict[str, Any]] = {
    "smolvlm": {
        "model": "SmolVLM-256M",
        "repo_id": "HuggingFaceTB/SmolVLM-256M-Instruct",
        "response_format": "plaintext",
    },
    "granite_vision": {
        "model": "Granite-Vision-3.3-2B",
        "repo_id": "ibm-granite/granite-vision-3.3-2b",
        "response_format": "plaintext",
    },
    "pixtral": {
        "model": "Pixtral-12B",
        "repo_id": "mistral-community/pixtral-12b",
        "response_format": "plaintext",
    },
    "qwen": {
        "model": "Qwen2.5-VL-3B-Instruct",
        "repo_id": "Qwen/Qwen2.5-VL-3B-Instruct",
        "response_format": "plaintext",
    },
}

STAGE_RUNTIMES: dict[str, dict[str, Any]] = {
    "layout": {
        "model": "docling-layout-heron-101",
        "runtime": "docling-ibm-models",
        "reason": "Layout detection is an object-detection stage, not a VLM stage.",
    },
    "ocr": {
        "model": "suryaocr",
        "runtime": "ocr-engine-specific",
        "reason": "OCR engines use their own runtimes and are not served by RemoteLLM.",
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
    remote_llm_supported: bool
    fallback_runtime: str | None = None
    fallback_reason: str | None = None
    response_format: str | None = None
    mode: str = "inline"

    def to_metadata(self) -> dict[str, Any]:
        return asdict(self)


def resolve_vlm_convert_runtime(settings: Settings) -> RuntimeResolution:
    return _resolve_runtime(
        stage=VLM_CONVERT_STAGE,
        model=settings.docling_vlm_model,
        requested_runtime=settings.docling_vlm_runtime,
        aliases=_VLM_CONVERT_ALIASES,
        presets=VLM_CONVERT_PRESETS,
        response_format=settings.docling_vlm_response_format,
    )


def resolve_picture_description_runtime(settings: Settings) -> RuntimeResolution:
    return _resolve_runtime(
        stage=PICTURE_DESCRIPTION_STAGE,
        model=settings.docling_pdf_picture_description_model,
        requested_runtime=settings.docling_pdf_picture_description_runtime,
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
            "local_runtimes": [RUNTIME_TRANSFORMERS, RUNTIME_AUTO_INLINE],
            "remote_runtime": RUNTIME_REMOTE_LLM,
            "remote_llm": {
                "provider": settings.docling_remote_llm_provider,
                "url": settings.docling_remote_llm_url,
                "model": settings.docling_remote_llm_model,
                "api_key_configured": settings.docling_remote_llm_api_key is not None,
                "api_key_header": settings.docling_remote_llm_api_key_header,
                "timeout_seconds": settings.docling_remote_llm_timeout_seconds,
                "concurrency": settings.docling_remote_llm_concurrency,
                "page_batch_size": settings.docling_remote_llm_page_batch_size,
                "max_tokens": settings.docling_remote_llm_max_tokens,
                "temperature": settings.docling_remote_llm_temperature,
                "health_check_enabled": settings.docling_remote_llm_health_check_enabled,
            },
            "docling_parse_concurrency": settings.effective_docling_parse_concurrency,
        },
        "active_pipeline_stage": (vlm_resolution.to_metadata() if pipeline == "vlm" else None),
        "stages": {
            VLM_CONVERT_STAGE: vlm_resolution.to_metadata(),
            PICTURE_DESCRIPTION_STAGE: picture_resolution.to_metadata(),
            "layout": STAGE_RUNTIMES["layout"]
            | {"model": settings.docling_pdf_layout_model},
            "ocr": STAGE_RUNTIMES["ocr"] | {"model": settings.docling_pdf_ocr_engine},
            "table_structure": _table_structure_metadata(settings),
            "picture_classifier": STAGE_RUNTIMES["picture_classifier"]
            | {"model": settings.docling_pdf_picture_classifier_preset},
            "code_formula": STAGE_RUNTIMES["code_formula"]
            | {"model": settings.docling_pdf_code_formula_preset},
        },
    }


def _resolve_runtime(
    *,
    stage: str,
    model: str,
    requested_runtime: str,
    aliases: dict[str, str],
    presets: dict[str, dict[str, Any]],
    response_format: str,
) -> RuntimeResolution:
    original_runtime = requested_runtime.strip().lower().replace("-", "_")
    normalized_model = _normalize_model_key(model)
    preset = aliases.get(normalized_model)
    preset_metadata = presets.get(preset or "")
    remote_llm_supported = True

    if original_runtime == RUNTIME_AUTO:
        resolved_runtime = RUNTIME_TRANSFORMERS
    elif original_runtime == RUNTIME_AUTO_INLINE:
        resolved_runtime = RUNTIME_AUTO_INLINE
    elif original_runtime == RUNTIME_REMOTE_LLM:
        resolved_runtime = RUNTIME_REMOTE_LLM
    else:
        resolved_runtime = original_runtime

    fallback_reason = None
    effective_fallback_runtime = None

    return RuntimeResolution(
        stage=stage,
        model=model,
        preset=preset,
        requested_runtime=original_runtime,
        resolved_runtime=resolved_runtime,
        remote_llm_supported=remote_llm_supported,
        fallback_runtime=effective_fallback_runtime,
        fallback_reason=fallback_reason,
        response_format=(
            str(preset_metadata.get("response_format"))
            if preset_metadata is not None
            else response_format
        ),
        mode="remote" if resolved_runtime == RUNTIME_REMOTE_LLM else "inline",
    )


def _table_structure_metadata(settings: Settings) -> dict[str, Any]:
    if settings.docling_pdf_table_structure_backend == "granite_vision":
        return {
            "model": settings.docling_pdf_table_structure_vlm_model,
            "runtime": "transformers",
            "remote_llm_supported": False,
            "reason": (
                "Docling catalog currently lists Granite Vision table structure "
                "with Transformers in the standard pipeline."
            ),
        }
    return STAGE_RUNTIMES["table_structure"] | {
        "model": settings.docling_pdf_table_structure_backend,
    }
