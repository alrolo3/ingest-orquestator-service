from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

_SAFE_NAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(filename: str | None) -> str:
    name = Path(filename or "uploaded-file").name
    cleaned = _SAFE_NAME_PATTERN.sub("-", name).strip(".-")
    return cleaned or "uploaded-file"


async def save_upload_file(
    upload: UploadFile,
    upload_dir: Path,
    *,
    job_id: str | None = None,
) -> Path:
    upload_dir.mkdir(parents=True, exist_ok=True)
    prefix = job_id or str(uuid4())
    destination = upload_dir / f"{prefix}-{safe_filename(upload.filename)}"

    with destination.open("wb") as output_file:
        while chunk := await upload.read(1024 * 1024):
            output_file.write(chunk)

    await upload.seek(0)
    return destination
