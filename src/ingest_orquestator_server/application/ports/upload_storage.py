from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ingest_orquestator_server.application.ports.upload_file import UploadFileLike


class UploadStorage(Protocol):
    async def save(self, upload: UploadFileLike, upload_dir: Path, *, job_id: str) -> Path:
        """Persist an uploaded file and return the stored path."""
