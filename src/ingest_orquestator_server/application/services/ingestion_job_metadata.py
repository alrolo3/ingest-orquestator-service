from __future__ import annotations

from ingest_orquestator_server.application.exceptions import (
    UnsupportedDocumentFormatError,
    UnsupportedIngestionOptionError,
    UnsupportedPipelineError,
)


def build_request_metadata(
    *,
    pipeline: str | None,
    chunking_enabled: bool | None,
    chunking_strategy: str | None,
) -> dict[str, object]:
    metadata: dict[str, object] = {}
    if pipeline is not None:
        metadata["requested_pipeline"] = pipeline
    if chunking_enabled is not None:
        metadata["requested_chunking_enabled"] = chunking_enabled
    if chunking_strategy is not None:
        metadata["requested_chunking_strategy"] = chunking_strategy
    return metadata


def build_error_metadata(
    *,
    error_type: str,
    exc: Exception | None = None,
    include_validation_error: bool = False,
) -> dict[str, str]:
    metadata = {"error_type": error_type}
    if include_validation_error and isinstance(
        exc,
        UnsupportedDocumentFormatError
        | UnsupportedPipelineError
        | UnsupportedIngestionOptionError,
    ):
        metadata["validation_error"] = "true"
    return metadata
