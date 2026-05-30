from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JsonFileWriter:
    def write(self, path: Path, payload: dict[str, Any]) -> None:
        content = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        path.write_text(content, encoding="utf-8")
