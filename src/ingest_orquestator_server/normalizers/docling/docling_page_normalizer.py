from __future__ import annotations

from typing import Any

from ingest_orquestator_server.models.document_page import DocumentPage
from ingest_orquestator_server.normalizers.docling.docling_value_converters import (
    metadata_without,
    safe_int,
    to_float,
)


class DoclingPageNormalizer:
    def normalize(self, raw_pages: Any) -> list[DocumentPage]:
        if isinstance(raw_pages, dict):
            return self._normalize_dict_pages(raw_pages)

        if isinstance(raw_pages, list):
            return self._normalize_list_pages(raw_pages)

        return []

    def _normalize_dict_pages(self, raw_pages: dict[str, Any]) -> list[DocumentPage]:
        pages = []
        sorted_raw_pages = sorted(raw_pages.items(), key=lambda item: safe_int(item[0]))
        for page_key, page_payload in sorted_raw_pages:
            if not isinstance(page_payload, dict):
                continue
            size = page_payload.get("size") if isinstance(page_payload.get("size"), dict) else {}
            pages.append(
                DocumentPage(
                    page_number=safe_int(page_key),
                    width=to_float(size.get("width")),
                    height=to_float(size.get("height")),
                    metadata=metadata_without(page_payload, {"size"}),
                )
            )
        return pages

    def _normalize_list_pages(self, raw_pages: list[Any]) -> list[DocumentPage]:
        pages = []
        for index, page_payload in enumerate(raw_pages, start=1):
            if not isinstance(page_payload, dict):
                continue
            page_number = safe_int(
                page_payload.get("page_no") or page_payload.get("page_number") or index
            )
            size = page_payload.get("size") if isinstance(page_payload.get("size"), dict) else {}
            pages.append(
                DocumentPage(
                    page_number=page_number,
                    width=to_float(size.get("width")),
                    height=to_float(size.get("height")),
                    metadata=metadata_without(page_payload, {"size"}),
                )
            )
        return pages
