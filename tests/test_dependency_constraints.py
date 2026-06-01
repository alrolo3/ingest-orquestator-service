from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from ingest_orquestator_server.config import Settings
from ingest_orquestator_server.infrastructure.docling import docling_model_options
from ingest_orquestator_server.infrastructure.docling.docling_model_options import (
    _validate_surya_transformers_compatibility,
)

TRANSFORMERS_PIN = "transformers>=4.57,<5"
OPENCV_RUNTIME_APT_PACKAGES = {
    "libgl1",
    "libglib2.0-0",
    "libsm6",
    "libxext6",
    "libxrender1",
    "libxcb1",
}


def test_transformers_pin_keeps_surya_and_qwen3_compatible() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text())
    requirements = Path("requirements.txt").read_text().splitlines()

    assert TRANSFORMERS_PIN in project["project"]["dependencies"]
    assert TRANSFORMERS_PIN in requirements


@pytest.mark.parametrize("dockerfile", ["Dockerfile", "Dockerfile.gpu"])
def test_dockerfiles_install_opencv_runtime_libraries(dockerfile: str) -> None:
    contents = Path(dockerfile).read_text()

    for package in OPENCV_RUNTIME_APT_PACKAGES:
        assert package in contents
    assert "import cv2" in contents
    assert "VIRTUAL_ENV=/opt/venv" in contents
    assert 'python -m venv "${VIRTUAL_ENV}"' in contents


def test_surya_ocr_rejects_transformers_5(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        docling_model_options,
        "_get_installed_distribution_version",
        lambda _: "5.9.0",
    )

    with pytest.raises(RuntimeError, match="SuryaOCR is not compatible"):
        _validate_surya_transformers_compatibility(Settings(docling_pdf_ocr_engine="suryaocr"))


def test_non_surya_ocr_allows_transformers_5(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        docling_model_options,
        "_get_installed_distribution_version",
        lambda _: "5.9.0",
    )

    _validate_surya_transformers_compatibility(Settings(docling_pdf_ocr_engine="auto"))
