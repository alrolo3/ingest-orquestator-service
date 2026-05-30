from __future__ import annotations

import re
from pathlib import Path

_SAFE_NAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


class FilenameSanitizer:
    def sanitize(self, filename: str | None) -> str:
        name = Path(filename or "uploaded-file").name
        cleaned = _SAFE_NAME_PATTERN.sub("-", name).strip(".-")
        return cleaned or "uploaded-file"
