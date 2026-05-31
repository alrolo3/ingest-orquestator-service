from ingest_orquestator_server.config import Settings
from ingest_orquestator_server.infrastructure.docling.docling_runtime_capabilities import (
    docling_runtime_metadata,
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


def test_runtime_metadata_does_not_advertise_legacy_vllm_compatibility() -> None:
    metadata = docling_runtime_metadata(Settings(), pipeline="standard")

    assert "legacy_vllm_env_compatibility" not in metadata["policy"]
    assert "legacy_vllm_alias" not in metadata["stages"]["vlm_convert"]
    assert "legacy_vllm_alias" not in metadata["stages"]["picture_description"]
