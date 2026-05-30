from __future__ import annotations

import re
from collections.abc import Iterable

from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.models.document_chunk import DocumentChunk
from ingest_orquestator_server.models.document_element import DocumentElement
from ingest_orquestator_server.models.parsed_document import ParsedDocument


class DocumentChunkingService:
    _excluded_types = {"page_header", "page_footer", "page_number", "watermark"}
    _excluded_content_layers = {"furniture"}

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def chunk(self, document: ParsedDocument) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        for element in self._iter_embeddable_elements(document.elements):
            text = self._element_text(element)
            if not text:
                continue

            for index, chunk_text in enumerate(self._split_text(text)):
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"{document.document_id}:{len(chunks) + 1}",
                        document_id=document.document_id,
                        page_start=element.page_number,
                        page_end=element.page_number,
                        text=chunk_text,
                        metadata={
                            "source_file_name": document.source_file_name,
                            "element_ids": [element.element_id],
                            "element_types": [element.type],
                            "parser": document.metadata.get("docling_options", {}).get(
                                "parser", "docling"
                            ),
                            "chunk_index_for_element": index,
                        },
                    )
                )
        return chunks

    def _iter_embeddable_elements(
        self,
        elements: list[DocumentElement],
    ) -> Iterable[DocumentElement]:
        for element in elements:
            content_layer = str(element.metadata.get("content_layer", "")).lower()
            label = str(element.metadata.get("label", "")).lower()
            if element.type in self._excluded_types or label in self._excluded_types:
                continue
            if content_layer in self._excluded_content_layers:
                continue
            yield element

    @staticmethod
    def _element_text(element: DocumentElement) -> str:
        if element.type == "table" and element.markdown:
            return element.markdown.strip()
        return (element.text or element.markdown or "").strip()

    def _split_text(self, text: str) -> list[str]:
        normalized_text = re.sub(r"\n{3,}", "\n\n", text.strip())
        if len(normalized_text) <= self._settings.chunk_size_chars:
            return [normalized_text]

        chunks = []
        start = 0
        while start < len(normalized_text):
            end = min(start + self._settings.chunk_size_chars, len(normalized_text))
            if end < len(normalized_text):
                paragraph_break = normalized_text.rfind("\n\n", start, end)
                sentence_break = normalized_text.rfind(". ", start, end)
                split_at = max(paragraph_break, sentence_break)
                if split_at > start:
                    end = split_at + 1

            chunk = normalized_text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            if end >= len(normalized_text):
                break
            start = max(end - self._settings.chunk_overlap_chars, start + 1)

        return chunks
