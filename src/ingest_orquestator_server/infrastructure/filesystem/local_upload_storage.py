from __future__ import annotations

from pathlib import Path

from ingest_orquestator_server.application.ports.upload_file import UploadFileLike
from ingest_orquestator_server.application.validation.upload_validator import UploadValidator
from ingest_orquestator_server.infrastructure.filesystem.filename_sanitizer import (
    FilenameSanitizer,
)


class LocalUploadStorage:
    def __init__(
        self,
        *,
        filename_sanitizer: FilenameSanitizer | None = None,
        upload_validator: UploadValidator | None = None,
    ) -> None:
        self._filename_sanitizer = filename_sanitizer or FilenameSanitizer()
        self._upload_validator = upload_validator

    async def save(self, upload: UploadFileLike, upload_dir: Path, *, job_id: str) -> Path:
        upload_dir.mkdir(parents=True, exist_ok=True)
        filename = self._filename_sanitizer.sanitize(upload.filename)
        destination = upload_dir / f"{job_id}-{filename}"

        bytes_written = 0
        try:
            with destination.open("wb") as output_file:
                while chunk := await upload.read(1024 * 1024):
                    bytes_written += len(chunk)
                    if self._upload_validator is not None:
                        self._upload_validator.validate_size(bytes_written)
                    output_file.write(chunk)
        except Exception:
            if destination.exists():
                destination.unlink()
            raise

        await upload.seek(0)
        return destination
