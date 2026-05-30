from __future__ import annotations

from pathlib import Path

from ingest_orquestator_server.application.ports.upload_file import UploadFileLike
from ingest_orquestator_server.infrastructure.filesystem.filename_sanitizer import (
    FilenameSanitizer,
)


class LocalUploadStorage:
    def __init__(self, filename_sanitizer: FilenameSanitizer | None = None) -> None:
        self._filename_sanitizer = filename_sanitizer or FilenameSanitizer()

    async def save(self, upload: UploadFileLike, upload_dir: Path, *, job_id: str) -> Path:
        upload_dir.mkdir(parents=True, exist_ok=True)
        filename = self._filename_sanitizer.sanitize(upload.filename)
        destination = upload_dir / f"{job_id}-{filename}"

        with destination.open("wb") as output_file:
            while chunk := await upload.read(1024 * 1024):
                output_file.write(chunk)

        await upload.seek(0)
        return destination
