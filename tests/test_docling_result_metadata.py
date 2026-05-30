from types import SimpleNamespace

from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.docling.docling_result_metadata import (
    conversion_result_metadata,
)


def test_conversion_result_metadata_summarizes_confidence() -> None:
    result = SimpleNamespace(
        status="success",
        errors=[],
        timings={"total": SimpleNamespace(elapsed=1.2)},
        confidence={
            "parse_score": 0.92,
            "mean_score": 0.72,
            "pages": {"1": {"mean_score": 0.72}},
        },
    )

    metadata = conversion_result_metadata(
        result,
        Settings(confidence_min_document_score=0.8),
    )

    assert metadata["status"] == "success"
    assert metadata["confidence_summary"]["mean_score"] == 0.72
    assert metadata["confidence_summary"]["page_count"] == 1
    assert metadata["warnings"][0]["kind"] == "confidence_below_threshold"


def test_conversion_result_metadata_respects_disabled_confidence_output() -> None:
    result = SimpleNamespace(confidence={"mean_score": 0.5})

    metadata = conversion_result_metadata(
        result,
        Settings(confidence_output_enabled=False),
    )

    assert metadata["confidence"] is None
    assert metadata["confidence_summary"] == {}
    assert metadata["warnings"] == []
