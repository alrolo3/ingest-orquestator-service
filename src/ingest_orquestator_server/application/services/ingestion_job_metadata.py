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
    dispatch_sink_mode: str | None = None,
    ocr_enabled: bool | None = None,
    ocr_languages: list[str] | None = None,
    include_html: bool = False,
) -> dict[str, object]:
    metadata: dict[str, object] = {}
    if pipeline is not None:
        metadata["requested_pipeline"] = pipeline
    if chunking_enabled is not None:
        metadata["requested_chunking_enabled"] = chunking_enabled
    if chunking_strategy is not None:
        metadata["requested_chunking_strategy"] = chunking_strategy
    if dispatch_sink_mode is not None:
        metadata["requested_dispatch_sink_mode"] = dispatch_sink_mode
    if ocr_enabled is not None:
        metadata["requested_ocr_enabled"] = ocr_enabled
    if ocr_languages is not None:
        metadata["requested_ocr_languages"] = ocr_languages
    metadata["requested_include_html"] = include_html
    return metadata


def build_error_metadata(
    *,
    error_type: str,
    exc: BaseException | None = None,
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
