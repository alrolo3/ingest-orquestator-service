import asyncio
from pathlib import Path

import pytest

from ingest_orquestator_server.application.exceptions import UploadValidationError
from ingest_orquestator_server.application.validation.upload_validator import UploadValidator
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.filesystem.local_upload_storage import (
    LocalUploadStorage,
)


class FakeUpload:
    def __init__(self, filename: str, chunks: list[bytes]) -> None:
        self.filename = filename
        self.content_type = None
        self._chunks = chunks
        self._index = 0

    async def read(self, size: int = -1) -> bytes:
        if self._index >= len(self._chunks):
            return b""
        chunk = self._chunks[self._index]
        self._index += 1
        return chunk

    async def seek(self, offset: int) -> None:
        self._index = 0


def test_upload_validator_rejects_unsupported_extension() -> None:
    validator = UploadValidator(Settings(allowed_upload_extensions=[".pdf"]))

    with pytest.raises(UploadValidationError):
        validator.validate_metadata(FakeUpload("example.exe", [b""]))


def test_upload_storage_rejects_oversized_upload(tmp_path: Path) -> None:
    validator = UploadValidator(Settings(max_upload_size_mb=1))
    upload = FakeUpload("example.pdf", [b"x" * (1024 * 1024 + 1)])

    async def save_upload() -> None:
        await LocalUploadStorage(upload_validator=validator).save(
            upload,
            tmp_path,
            job_id="job-1",
        )

    with pytest.raises(UploadValidationError):
        asyncio.run(save_upload())

    assert list(tmp_path.iterdir()) == []
