from __future__ import annotations

from pathlib import Path

from ingest_orquestator_server.application.exceptions import UploadValidationError
from ingest_orquestator_server.application.ports.upload_file import UploadFileLike
from ingest_orquestator_server.config.settings import Settings


class UploadValidator:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def validate_metadata(self, upload: UploadFileLike) -> None:
        filename = upload.filename or ""
        extension = Path(filename).suffix.lower()
        allowed_extensions = set(self._settings.allowed_upload_extensions)
        if extension not in allowed_extensions:
            allowed = ", ".join(sorted(allowed_extensions))
            raise UploadValidationError(
                f"Unsupported file type '{extension or '<none>'}'. Allowed extensions: {allowed}",
                status_code=400,
            )

    def validate_size(self, size_bytes: int) -> None:
        if size_bytes > self._settings.max_upload_size_bytes:
            raise UploadValidationError(
                (
                    f"Upload exceeds {self._settings.max_upload_size_mb} MB limit "
                    f"({size_bytes} bytes received)"
                ),
                status_code=413,
            )
