import pytest

from ingest_orquestator_server.infrastructure.docling.ocr_engine_registry import (
    OcrEngineRegistry,
)


def test_ocr_registry_lists_docling_engines() -> None:
    engines = OcrEngineRegistry(allow_external_plugins=False).available_engines()

    assert "auto" in engines


def test_ocr_registry_unknown_engine_error_lists_available_engines() -> None:
    registry = OcrEngineRegistry(allow_external_plugins=False)

    with pytest.raises(RuntimeError, match="Available engines"):
        registry.create_options("missing-ocr-engine")
