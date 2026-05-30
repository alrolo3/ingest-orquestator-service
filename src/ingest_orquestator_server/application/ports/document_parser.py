from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ingest_orquestator_server.models.parse_output import ParseOutput


class DocumentParser(Protocol):
    name: str

    def parse(self, file_path: Path, *, document_id: str | None = None) -> ParseOutput:
        """Parse a source file into raw and normalized output."""
