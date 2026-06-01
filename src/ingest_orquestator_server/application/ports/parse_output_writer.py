from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ingest_orquestator_server.models.output_files import OutputFiles
from ingest_orquestator_server.models.parse_diagnostics import ParseDiagnostics
from ingest_orquestator_server.models.parsed_document_content import ParsedDocumentContent


class ParseOutputWriter(Protocol):
    def write(
        self,
        content: ParsedDocumentContent,
        output_root: Path,
        *,
        diagnostics: ParseDiagnostics | None = None,
    ) -> OutputFiles:
        """Persist parse artifacts and return their paths."""
