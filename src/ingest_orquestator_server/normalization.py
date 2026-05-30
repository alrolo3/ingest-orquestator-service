from __future__ import annotations

from pathlib import Path
from typing import Any

from ingest_orquestator_server.models import DocumentElement, DocumentPage, ParsedDocument

_COLLECTION_TYPES = {
    "texts": "text",
    "tables": "table",
    "pictures": "image",
    "key_value_items": "key_value",
    "form_items": "form",
}


def normalize_docling_document(
    *,
    raw_docling: dict[str, Any],
    source_path: Path,
    document_id: str,
    markdown: str,
    text: str,
    mime_type: str | None,
) -> ParsedDocument:
    pages = _normalize_pages(raw_docling.get("pages"))
    elements = _normalize_elements(raw_docling)
    origin = raw_docling.get("origin") if isinstance(raw_docling.get("origin"), dict) else {}
    source_file_name = str(origin.get("filename") or source_path.name)

    return ParsedDocument(
        document_id=document_id,
        source_file_name=source_file_name,
        source_path=str(source_path),
        mime_type=(
            str(origin.get("mimetype") or mime_type)
            if origin.get("mimetype") or mime_type
            else None
        ),
        title=_guess_title(raw_docling, elements, source_path),
        page_count=len(pages),
        pages=pages,
        elements=elements,
        markdown=markdown,
        text=text,
        metadata={
            "schema_name": raw_docling.get("schema_name"),
            "version": raw_docling.get("version"),
            "origin": origin,
        },
    )


def _normalize_pages(raw_pages: Any) -> list[DocumentPage]:
    if isinstance(raw_pages, dict):
        pages = []
        sorted_raw_pages = sorted(raw_pages.items(), key=lambda item: _safe_int(item[0]))
        for page_key, page_payload in sorted_raw_pages:
            if not isinstance(page_payload, dict):
                continue
            size = page_payload.get("size") if isinstance(page_payload.get("size"), dict) else {}
            pages.append(
                DocumentPage(
                    page_number=_safe_int(page_key),
                    width=_to_float(size.get("width")),
                    height=_to_float(size.get("height")),
                    metadata=_metadata_without(page_payload, {"size"}),
                )
            )
        return pages

    if isinstance(raw_pages, list):
        pages = []
        for index, page_payload in enumerate(raw_pages, start=1):
            if not isinstance(page_payload, dict):
                continue
            page_number = _safe_int(
                page_payload.get("page_no") or page_payload.get("page_number") or index
            )
            size = page_payload.get("size") if isinstance(page_payload.get("size"), dict) else {}
            pages.append(
                DocumentPage(
                    page_number=page_number,
                    width=_to_float(size.get("width")),
                    height=_to_float(size.get("height")),
                    metadata=_metadata_without(page_payload, {"size"}),
                )
            )
        return pages

    return []


def _normalize_elements(raw_docling: dict[str, Any]) -> list[DocumentElement]:
    elements: list[DocumentElement] = []
    sequence = 0

    for collection_name, fallback_type in _COLLECTION_TYPES.items():
        collection = raw_docling.get(collection_name)
        if not isinstance(collection, list):
            continue

        for index, item in enumerate(collection):
            if not isinstance(item, dict):
                continue

            label = str(item.get("label") or fallback_type)
            element_type = _map_element_type(collection_name, label, fallback_type)
            text = _extract_text(item, collection_name)
            markdown = _table_to_markdown(item) if collection_name == "tables" else None
            prov = _first_provenance(item)

            elements.append(
                DocumentElement(
                    element_id=str(item.get("self_ref") or f"{collection_name}/{index}"),
                    type=element_type,
                    page_number=_to_int(prov.get("page_no") or prov.get("page_number")),
                    text=text,
                    markdown=markdown,
                    bbox=prov.get("bbox") if isinstance(prov.get("bbox"), dict) else None,
                    confidence=_to_float(item.get("confidence") or prov.get("confidence")),
                    metadata=_metadata_without(
                        item,
                        {
                            "text",
                            "orig",
                            "prov",
                            "data",
                            "image",
                            "annotations",
                        },
                    )
                    | {
                        "collection": collection_name,
                        "label": label,
                        "provenance": item.get("prov", []),
                        "sequence": sequence,
                    },
                )
            )
            sequence += 1

    elements.sort(key=lambda item: (item.page_number or 0, item.metadata["sequence"]))
    return elements


def _map_element_type(collection_name: str, label: str, fallback_type: str) -> str:
    normalized_label = label.lower().replace("-", "_")
    if collection_name == "texts":
        if "title" in normalized_label:
            return "title"
        if "header" in normalized_label:
            return "heading"
        if "list" in normalized_label:
            return "list"
    return fallback_type


def _extract_text(item: dict[str, Any], collection_name: str) -> str | None:
    for key in ("text", "orig", "caption"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value

    if collection_name == "tables":
        return _table_to_plain_text(item)

    return None


def _table_to_plain_text(item: dict[str, Any]) -> str | None:
    cells = _table_cells(item)
    cell_text = [
        str(cell.get("text", "")).strip() for cell in cells if str(cell.get("text", "")).strip()
    ]
    return "\n".join(cell_text) if cell_text else None


def _table_to_markdown(item: dict[str, Any]) -> str | None:
    cells = _table_cells(item)
    if not cells:
        return None

    max_row = max(_safe_int(cell.get("end_row_offset_idx", 1)) for cell in cells)
    max_col = max(_safe_int(cell.get("end_col_offset_idx", 1)) for cell in cells)
    if max_row <= 0 or max_col <= 0:
        return None

    grid = [["" for _ in range(max_col)] for _ in range(max_row)]
    for cell in cells:
        row = max(_safe_int(cell.get("start_row_offset_idx", 0)), 0)
        col = max(_safe_int(cell.get("start_col_offset_idx", 0)), 0)
        if row < max_row and col < max_col:
            grid[row][col] = str(cell.get("text", "")).strip()

    header = grid[0]
    separator = ["---" for _ in header]
    body = grid[1:] or [["" for _ in header]]
    rows = [header, separator, *body]
    return "\n".join("| " + " | ".join(row) + " |" for row in rows)


def _table_cells(item: dict[str, Any]) -> list[dict[str, Any]]:
    data = item.get("data")
    if not isinstance(data, dict):
        return []
    cells = data.get("table_cells")
    if not isinstance(cells, list):
        return []
    return [cell for cell in cells if isinstance(cell, dict)]


def _first_provenance(item: dict[str, Any]) -> dict[str, Any]:
    provenance = item.get("prov")
    if isinstance(provenance, list) and provenance and isinstance(provenance[0], dict):
        return provenance[0]
    return {}


def _guess_title(
    raw_docling: dict[str, Any],
    elements: list[DocumentElement],
    source_path: Path,
) -> str:
    name = raw_docling.get("name")
    if isinstance(name, str) and name.strip():
        return name

    for element in elements:
        if element.type == "title" and element.text:
            return element.text.strip()

    return source_path.stem


def _metadata_without(payload: dict[str, Any], excluded_keys: set[str]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key not in excluded_keys}


def _safe_int(value: Any) -> int:
    converted = _to_int(value)
    return converted if converted is not None else 0


def _to_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
