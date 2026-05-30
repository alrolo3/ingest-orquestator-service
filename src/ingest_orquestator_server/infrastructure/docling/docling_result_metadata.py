from __future__ import annotations

import math
from typing import Any

from ingest_orquestator_server.config.settings import Settings


def conversion_result_metadata(result: Any, settings: Settings) -> dict[str, Any]:
    confidence = (
        _safe_dump(getattr(result, "confidence", None))
        if settings.confidence_output_enabled
        else None
    )
    summary = _confidence_summary(confidence) if settings.confidence_output_enabled else {}
    warnings = _confidence_warnings(summary, settings) if settings.confidence_output_enabled else []
    return {
        "status": _enum_value(getattr(result, "status", None)),
        "errors": _safe_dump(getattr(result, "errors", [])),
        "timings": _safe_dump(getattr(result, "timings", {})),
        "confidence": confidence,
        "confidence_summary": summary,
        "warnings": warnings,
    }


def _confidence_summary(confidence: dict[str, Any] | None) -> dict[str, Any]:
    confidence = confidence or {}
    return {
        "parse_score": confidence.get("parse_score"),
        "layout_score": confidence.get("layout_score"),
        "table_score": confidence.get("table_score"),
        "ocr_score": confidence.get("ocr_score"),
        "mean_score": confidence.get("mean_score"),
        "low_score": confidence.get("low_score"),
        "mean_grade": _enum_value(confidence.get("mean_grade")),
        "low_grade": _enum_value(confidence.get("low_grade")),
        "page_count": len(confidence.get("pages") or {}),
    }


def _confidence_warnings(
    summary: dict[str, Any],
    settings: Settings,
) -> list[dict[str, Any]]:
    warnings = []
    threshold = settings.confidence_min_document_score
    mean_score = summary.get("mean_score")
    if threshold is not None and isinstance(mean_score, int | float) and mean_score < threshold:
        warnings.append(
            {
                "kind": "confidence_below_threshold",
                "score": mean_score,
                "threshold": threshold,
                "warn_only": settings.confidence_warn_only,
            }
        )
    return warnings


def _safe_dump(value: Any) -> Any:
    if value is None:
        return None
    enum_value = _enum_value(value)
    if enum_value is not value:
        return enum_value
    if hasattr(value, "model_dump"):
        return _safe_dump(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {str(_enum_value(key)): _safe_dump(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [_safe_dump(item) for item in value]
    if hasattr(value, "__dict__"):
        return _safe_dump(vars(value))
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)
