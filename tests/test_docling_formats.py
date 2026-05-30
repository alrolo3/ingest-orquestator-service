from pathlib import Path

import pytest

from ingest_orquestator_server.application.exceptions import (
    UnsupportedDocumentFormatError,
    UnsupportedPipelineError,
)
from ingest_orquestator_server.infrastructure.docling.docling_formats import (
    detect_input_format,
    resolve_pipeline_mode,
    validate_allowed_format,
)


def test_detect_input_format_maps_common_extensions() -> None:
    assert detect_input_format(Path("document.pdf")) == "pdf"
    assert detect_input_format(Path("document.docx")) == "docx"
    assert detect_input_format(Path("slides.pptx")) == "pptx"
    assert detect_input_format(Path("table.csv")) == "csv"
    assert detect_input_format(Path("image.png")) == "image"
    assert detect_input_format(Path("notes.markdown")) == "md"
    assert detect_input_format(Path("notes.txt")) == "md"


def test_detect_input_format_rejects_unknown_extension() -> None:
    with pytest.raises(UnsupportedDocumentFormatError):
        detect_input_format(Path("document.unknown"))


def test_validate_allowed_format_rejects_disabled_format() -> None:
    with pytest.raises(UnsupportedDocumentFormatError, match="disabled"):
        validate_allowed_format("docx", ["pdf"])


def test_resolve_pipeline_mode_support_matrix() -> None:
    assert resolve_pipeline_mode("standard", "docx") == "standard"
    assert resolve_pipeline_mode("vlm", "pdf") == "vlm"
    assert resolve_pipeline_mode("vlm", "image") == "vlm"
    assert resolve_pipeline_mode("auto", "pdf") == "standard"

    with pytest.raises(UnsupportedPipelineError, match="PDF and image"):
        resolve_pipeline_mode("vlm", "docx")
