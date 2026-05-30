import pytest

from ingest_orquestator_server.config import Settings
from ingest_orquestator_server.infrastructure.docling.docling_runtime_capabilities import (
    resolve_picture_description_runtime,
    resolve_vlm_convert_runtime,
)


def test_vlm_convert_resolves_vllm_for_supported_preset() -> None:
    resolution = resolve_vlm_convert_runtime(
        Settings(
            docling_vlm_model="granite_vision",
            docling_vlm_runtime="vllm",
        )
    )

    assert resolution.preset == "granite_vision"
    assert resolution.vllm_supported is True
    assert resolution.resolved_runtime == "vllm"
    assert resolution.fallback_reason is None


def test_vlm_convert_falls_back_for_qwen3_when_vllm_is_requested() -> None:
    resolution = resolve_vlm_convert_runtime(
        Settings(
            docling_vlm_model="Qwen/Qwen3-VL-8B-Instruct",
            docling_vlm_runtime="vllm",
        )
    )

    assert resolution.preset is None
    assert resolution.vllm_supported is False
    assert resolution.resolved_runtime == "transformers"
    assert resolution.fallback_runtime == "transformers"
    assert "not list" in str(resolution.fallback_reason)


def test_vlm_convert_can_reject_unsupported_vllm_without_fallback() -> None:
    with pytest.raises(ValueError, match="not documented as vLLM-capable"):
        resolve_vlm_convert_runtime(
            Settings(
                docling_vlm_model="Qwen/Qwen3-VL-8B-Instruct",
                docling_vlm_runtime="vllm",
                docling_vllm_fallback_on_unsupported=False,
            )
        )


def test_picture_description_resolves_vllm_for_granite_vision() -> None:
    resolution = resolve_picture_description_runtime(
        Settings(
            docling_pdf_picture_description_model="granite_vision",
            docling_pdf_picture_description_runtime="vllm",
        )
    )

    assert resolution.preset == "granite_vision"
    assert resolution.resolved_runtime == "vllm"
    assert resolution.response_format == "plaintext"


def test_picture_description_custom_model_can_opt_into_unverified_vllm() -> None:
    resolution = resolve_picture_description_runtime(
        Settings(
            docling_pdf_picture_description_model="Qwen/Qwen3-VL-8B-Instruct",
            docling_pdf_picture_description_runtime="vllm",
            docling_vllm_allow_unverified_models=True,
        )
    )

    assert resolution.preset is None
    assert resolution.vllm_supported is True
    assert resolution.resolved_runtime == "vllm"
    assert resolution.allow_unverified_vllm_model is True
