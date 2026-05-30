from __future__ import annotations

from pathlib import Path
from typing import Any

from ingest_orquestator_server.models.parsed_document import ParsedDocument
from ingest_orquestator_server.normalizers.docling.docling_element_normalizer import (
    DoclingElementNormalizer,
)
from ingest_orquestator_server.normalizers.docling.docling_page_normalizer import (
    DoclingPageNormalizer,
)


class DoclingDocumentNormalizer:
    def __init__(
        self,
        *,
        page_normalizer: DoclingPageNormalizer | None = None,
        element_normalizer: DoclingElementNormalizer | None = None,
    ) -> None:
        self._page_normalizer = page_normalizer or DoclingPageNormalizer()
        self._element_normalizer = element_normalizer or DoclingElementNormalizer()

    def normalize(
        self,
        *,
        raw_docling: dict[str, Any],
        source_path: Path,
        document_id: str,
        markdown: str,
        text: str,
        mime_type: str | None,
    ) -> ParsedDocument:
        pages = self._page_normalizer.normalize(raw_docling.get("pages"))
        elements = self._element_normalizer.normalize(raw_docling)
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
            title=self._guess_title(raw_docling, elements, source_path),
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

    @staticmethod
    def _guess_title(raw_docling: dict[str, Any], elements: list[Any], source_path: Path) -> str:
        name = raw_docling.get("name")
        if isinstance(name, str) and name.strip():
            return name

        for element in elements:
            if element.type == "title" and element.text:
                return element.text.strip()

        return source_path.stem
