from __future__ import annotations

from typing import Any


def metadata_without(payload: dict[str, Any], excluded_keys: set[str]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key not in excluded_keys}


def safe_int(value: Any) -> int:
    converted = to_int(value)
    return converted if converted is not None else 0


def to_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
