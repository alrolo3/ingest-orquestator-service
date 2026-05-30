import pytest
from pydantic import ValidationError

from ingest_orquestator_server.config import Settings


def test_settings_accept_cuda_device() -> None:
    settings = Settings(docling_accelerator_device="CUDA:1")

    assert settings.docling_accelerator_device == "cuda:1"


def test_settings_reject_unknown_accelerator_device() -> None:
    with pytest.raises(ValidationError):
        Settings(docling_accelerator_device="gpu")


def test_settings_parse_allowed_upload_extensions_from_string() -> None:
    settings = Settings(allowed_upload_extensions=".PDF, md, .txt")

    assert settings.allowed_upload_extensions == [".md", ".pdf", ".txt"]
