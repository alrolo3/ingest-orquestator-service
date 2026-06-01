from ingest_orquestator_server.config import Settings
from ingest_orquestator_server.infrastructure.docling.docling_runtime_capabilities import (
    docling_runtime_metadata,
    resolve_picture_description_runtime,
    resolve_vlm_convert_runtime,
)


def test_vlm_convert_resolves_remote_llm_by_default() -> None:
    resolution = resolve_vlm_convert_runtime(
        Settings(
            docling_vlm_model="Qwen/Qwen3-VL-8B-Instruct",
        )
    )

    assert resolution.preset is None
    assert resolution.remote_llm_supported is True
    assert resolution.resolved_runtime == "remote_llm"
    assert resolution.mode == "remote"


def test_vlm_convert_does_not_resolve_local_runtime() -> None:
    resolution = resolve_vlm_convert_runtime(
        Settings(
            docling_vlm_model="Qwen/Qwen3-VL-8B-Instruct",
        )
    )

    assert resolution.requested_runtime == "remote_llm"
    assert resolution.resolved_runtime == "remote_llm"
    assert resolution.mode == "remote"


def test_picture_description_resolves_remote_llm() -> None:
    resolution = resolve_picture_description_runtime(
        Settings(
            docling_vlm_model="granite_vision",
        )
    )

    assert resolution.preset == "granite_vision"
    assert resolution.resolved_runtime == "remote_llm"
    assert resolution.response_format == "plaintext"


def test_runtime_metadata_does_not_advertise_legacy_vllm_compatibility() -> None:
    metadata = docling_runtime_metadata(Settings(), pipeline="standard")

    assert metadata["policy"]["backend_vlm_loading"] == "disabled"
    assert "local_runtimes" not in metadata["policy"]
    assert "legacy_vllm_env_compatibility" not in metadata["policy"]
    assert "legacy_vllm_alias" not in metadata["stages"]["vlm_convert"]
    assert "legacy_vllm_alias" not in metadata["stages"]["picture_description"]
