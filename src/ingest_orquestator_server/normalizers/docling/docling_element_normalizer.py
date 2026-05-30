from __future__ import annotations

from typing import Any

from ingest_orquestator_server.models.document_element import DocumentElement
from ingest_orquestator_server.normalizers.docling.docling_table_renderer import (
    DoclingTableRenderer,
)
from ingest_orquestator_server.normalizers.docling.docling_value_converters import (
    metadata_without,
    to_float,
    to_int,
)


class DoclingElementNormalizer:
    _collection_types = {
        "texts": "text",
        "tables": "table",
        "pictures": "image",
        "key_value_items": "key_value",
        "form_items": "form",
    }

    def __init__(self, table_renderer: DoclingTableRenderer | None = None) -> None:
        self._table_renderer = table_renderer or DoclingTableRenderer()

    def normalize(self, raw_docling: dict[str, Any]) -> list[DocumentElement]:
        elements: list[DocumentElement] = []
        sequence = 0

        for collection_name, fallback_type in self._collection_types.items():
            collection = raw_docling.get(collection_name)
            if not isinstance(collection, list):
                continue

            for index, item in enumerate(collection):
                if not isinstance(item, dict):
                    continue

                elements.append(
                    self._normalize_item(
                        collection_name=collection_name,
                        fallback_type=fallback_type,
                        index=index,
                        item=item,
                        sequence=sequence,
                    )
                )
                sequence += 1

        elements.sort(key=lambda item: (item.page_number or 0, item.metadata["sequence"]))
        return elements

    def _normalize_item(
        self,
        *,
        collection_name: str,
        fallback_type: str,
        index: int,
        item: dict[str, Any],
        sequence: int,
    ) -> DocumentElement:
        label = str(item.get("label") or fallback_type)
        provenance = self._first_provenance(item)

        return DocumentElement(
            element_id=str(item.get("self_ref") or f"{collection_name}/{index}"),
            type=self._map_element_type(collection_name, label, fallback_type),
            page_number=to_int(provenance.get("page_no") or provenance.get("page_number")),
            text=self._extract_text(item, collection_name),
            markdown=self._table_renderer.render_markdown(item)
            if collection_name == "tables"
            else None,
            bbox=provenance.get("bbox") if isinstance(provenance.get("bbox"), dict) else None,
            confidence=to_float(item.get("confidence") or provenance.get("confidence")),
            metadata=self._element_metadata(item, collection_name)
            | {
                "collection": collection_name,
                "label": label,
                "provenance": item.get("prov", []),
                "sequence": sequence,
            },
        )

    @staticmethod
    def _map_element_type(collection_name: str, label: str, fallback_type: str) -> str:
        normalized_label = label.lower().replace("-", "_")
        if collection_name == "texts":
            if normalized_label in {"page_header", "page_footer", "page_number"}:
                return normalized_label
            if "title" in normalized_label:
                return "title"
            if "header" in normalized_label:
                return "heading"
            if "list" in normalized_label:
                return "list"
        return fallback_type

    def _extract_text(self, item: dict[str, Any], collection_name: str) -> str | None:
        for key in ("text", "orig", "caption"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value

        if collection_name == "tables":
            return self._table_renderer.render_plain_text(item)

        return None

    @staticmethod
    def _first_provenance(item: dict[str, Any]) -> dict[str, Any]:
        provenance = item.get("prov")
        if isinstance(provenance, list) and provenance and isinstance(provenance[0], dict):
            return provenance[0]
        return {}

    @staticmethod
    def _element_metadata(item: dict[str, Any], collection_name: str) -> dict[str, Any]:
        excluded = {
            "text",
            "orig",
            "prov",
            "image",
            "annotations",
        }
        if collection_name != "tables":
            excluded.add("data")
        return metadata_without(item, excluded)
