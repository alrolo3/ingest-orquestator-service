from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("ingest_orquestator_server.stage")

_SENSITIVE_KEY_PARTS = {
    "authorization",
    "password",
    "secret",
    "token",
}


def log_stage(event: str, **fields: Any) -> None:
    payload = {
        "event": event,
        "timestamp": datetime.now(UTC).isoformat(),
        **{key: _sanitize(key, value) for key, value in fields.items() if value is not None},
    }
    logger.info(json.dumps(payload, sort_keys=True, default=str))


def _sanitize(key: str, value: Any) -> Any:
    if any(part in key.lower() for part in _SENSITIVE_KEY_PARTS):
        return "***"
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {
            nested_key: _sanitize(str(nested_key), nested_value)
            for nested_key, nested_value in value.items()
        }
    if isinstance(value, list | tuple | set):
        return [_sanitize(key, item) for item in value]
    if hasattr(value, "value"):
        return value.value
    return value
