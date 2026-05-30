from __future__ import annotations

from typing import Protocol


class UploadFileLike(Protocol):
    filename: str | None
    content_type: str | None

    async def read(self, size: int = -1) -> bytes:
        """Read upload bytes."""

    async def seek(self, offset: int) -> None:
        """Move the upload cursor."""
