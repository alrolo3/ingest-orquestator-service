from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

from ingest_orquestator_server.application.exceptions import (
    UnsupportedIngestionOptionError,
)

DISPATCH_SINK_MODES = ("local", "elastic", "local_and_elastic")
DEFAULT_OCR_LANGUAGE_OPTIONS = (
    ("en", "English"),
    ("es", "Spanish"),
    ("fr", "French"),
    ("de", "German"),
    ("it", "Italian"),
    ("pt", "Portuguese"),
)
_MAX_OCR_LANGUAGES = 8
_OCR_LANGUAGE_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{1,15}$")


def normalize_dispatch_sink_mode(value: str | None) -> str | None:
    if value is None or value.strip() == "":
        return None
    normalized = value.strip().lower()
    if normalized not in DISPATCH_SINK_MODES:
        raise UnsupportedIngestionOptionError(
            "dispatch_sink_mode must be one of local, elastic, or local_and_elastic"
        )
    return normalized


def normalize_ocr_languages(value: str | Iterable[str] | None) -> list[str] | None:
    if value is None:
        return None
    raw_values = value.split(",") if isinstance(value, str) else list(value)
    languages: list[str] = []
    seen: set[str] = set()
    for raw_language in raw_values:
        language = str(raw_language).strip().lower()
        if not language or language in seen:
            continue
        if not _OCR_LANGUAGE_PATTERN.fullmatch(language):
            raise UnsupportedIngestionOptionError(
                "ocr_languages must be comma-separated language codes such as en or es"
            )
        seen.add(language)
        languages.append(language)

    if not languages:
        return None
    if len(languages) > _MAX_OCR_LANGUAGES:
        raise UnsupportedIngestionOptionError(
            f"ocr_languages accepts at most {_MAX_OCR_LANGUAGES} language codes"
        )
    return languages


def dispatch_sink_mode_from_metadata(
    metadata: Mapping[str, object],
    *,
    default: str,
) -> str:
    requested = metadata.get("requested_dispatch_sink_mode")
    if isinstance(requested, str):
        return normalize_dispatch_sink_mode(requested) or default
    return default


def ocr_languages_from_metadata(metadata: Mapping[str, object]) -> list[str] | None:
    requested = metadata.get("requested_ocr_languages")
    if isinstance(requested, str):
        return normalize_ocr_languages(requested)
    if isinstance(requested, list):
        return normalize_ocr_languages([str(item) for item in requested])
    return None
