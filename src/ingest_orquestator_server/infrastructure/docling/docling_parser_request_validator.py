from __future__ import annotations

from pathlib import Path

from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.docling.docling_formats import (
    detect_input_format,
    resolve_pipeline_mode,
    validate_allowed_format,
)


class DoclingParserRequestValidator:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def validate(
        self,
        *,
        filename: str,
        pipeline: str | None,
    ) -> None:
        input_format = detect_input_format(Path(filename))
        validate_allowed_format(input_format, self._settings.docling_allowed_formats)
        resolve_pipeline_mode(pipeline or self._settings.docling_pipeline, input_format)
