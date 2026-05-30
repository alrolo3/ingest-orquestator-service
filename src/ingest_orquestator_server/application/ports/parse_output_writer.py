from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ingest_orquestator_server.models.output_files import OutputFiles
from ingest_orquestator_server.models.parse_output import ParseOutput


class ParseOutputWriter(Protocol):
    def write(self, parse_output: ParseOutput, output_root: Path) -> OutputFiles:
        """Persist parse artifacts and return their paths."""
