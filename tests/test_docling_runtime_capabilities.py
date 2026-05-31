from ingest_orquestator_server.config import Settings
from ingest_orquestator_server.infrastructure.docling.docling_runtime_capabilities import (
    resolve_picture_description_runtime,
    resolve_vlm_convert_runtime,
)


def test_vlm_convert_resolves_remote_llm_for_new_runtime_name() -> None:
    resolution = resolve_vlm_convert_runtime(
        Settings(
            docling_vlm_model="Qwen/Qwen3-VL-8B-Instruct",
            docling_vlm_runtime="remote_llm",
        )
    )

    assert resolution.preset is None
    assert resolution.remote_llm_supported is True
    assert resolution.resolved_runtime == "remote_llm"
    assert resolution.mode == "remote"


def test_vlm_convert_treats_legacy_vllm_as_remote_llm_alias() -> None:
    settings = Settings(
        docling_vlm_model="granite_vision",
        docling_vlm_runtime="vllm",
    )
    resolution = resolve_vlm_convert_runtime(
        settings
    )

    assert settings.docling_vlm_runtime == "remote_llm"
    assert resolution.preset == "granite_vision"
    assert resolution.requested_runtime == "remote_llm"
    assert resolution.resolved_runtime == "remote_llm"
    assert resolution.legacy_vllm_alias is False


def test_auto_runtime_remains_local_transformers() -> None:
    resolution = resolve_vlm_convert_runtime(
        Settings(
            docling_vlm_model="Qwen/Qwen3-VL-8B-Instruct",
            docling_vlm_runtime="auto",
        )
    )

    assert resolution.resolved_runtime == "transformers"
    assert resolution.mode == "inline"


def test_picture_description_resolves_remote_llm() -> None:
    resolution = resolve_picture_description_runtime(
        Settings(
            docling_pdf_picture_description_model="granite_vision",
            docling_pdf_picture_description_runtime="remote_llm",
        )
    )

    assert resolution.preset == "granite_vision"
    assert resolution.resolved_runtime == "remote_llm"
    assert resolution.response_format == "plaintext"


def test_picture_description_legacy_vllm_alias_uses_remote_llm() -> None:
    settings = Settings(
        docling_pdf_picture_description_model="Qwen/Qwen3-VL-8B-Instruct",
        docling_pdf_picture_description_runtime="vllm",
    )
    resolution = resolve_picture_description_runtime(
        settings
    )

    assert settings.docling_pdf_picture_description_runtime == "remote_llm"
    assert resolution.preset is None
    assert resolution.resolved_runtime == "remote_llm"
    assert resolution.legacy_vllm_alias is False
