from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ingest_orquestator_server.models.parse_output import ParseOutput
from ingest_orquestator_server.models.parse_progress import ParseProgressCallback


class DocumentParser(Protocol):
    name: str

    def parse(
        self,
        file_path: Path,
        *,
        document_id: str | None = None,
        pipeline: str | None = None,
        ocr_enabled: bool | None = None,
        ocr_languages: list[str] | None = None,
        include_html: bool = False,
        progress_callback: ParseProgressCallback | None = None,
    ) -> ParseOutput:
        """Parse a source file into a parser-agnostic output."""
