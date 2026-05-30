from __future__ import annotations

from typing import Any

from ingest_orquestator_server.normalizers.docling.docling_value_converters import safe_int


class DoclingTableRenderer:
    def render_plain_text(self, item: dict[str, Any]) -> str | None:
        cells = self._table_cells(item)
        cell_text = [
            str(cell.get("text", "")).strip() for cell in cells if str(cell.get("text", "")).strip()
        ]
        return "\n".join(cell_text) if cell_text else None

    def render_markdown(self, item: dict[str, Any]) -> str | None:
        cells = self._table_cells(item)
        if not cells:
            return None

        max_row = max(safe_int(cell.get("end_row_offset_idx", 1)) for cell in cells)
        max_col = max(safe_int(cell.get("end_col_offset_idx", 1)) for cell in cells)
        if max_row <= 0 or max_col <= 0:
            return None

        grid = [["" for _ in range(max_col)] for _ in range(max_row)]
        for cell in cells:
            row = max(safe_int(cell.get("start_row_offset_idx", 0)), 0)
            col = max(safe_int(cell.get("start_col_offset_idx", 0)), 0)
            if row < max_row and col < max_col:
                grid[row][col] = str(cell.get("text", "")).strip()

        header = grid[0]
        separator = ["---" for _ in header]
        body = grid[1:] or [["" for _ in header]]
        rows = [header, separator, *body]
        return "\n".join("| " + " | ".join(row) + " |" for row in rows)

    @staticmethod
    def _table_cells(item: dict[str, Any]) -> list[dict[str, Any]]:
        data = item.get("data")
        if not isinstance(data, dict):
            return []
        cells = data.get("table_cells")
        if not isinstance(cells, list):
            return []
        return [cell for cell in cells if isinstance(cell, dict)]
