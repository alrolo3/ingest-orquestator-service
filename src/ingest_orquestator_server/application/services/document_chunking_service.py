from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from docling_core.transforms.chunker.tokenizer.base import BaseTokenizer

from ingest_orquestator_server.config.chunking import validate_chunking_strategy
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.models.document_chunk import DocumentChunk
from ingest_orquestator_server.models.document_element import DocumentElement
from ingest_orquestator_server.models.parsed_document import ParsedDocument


class DocumentChunkingService:
    _excluded_types = {"page_header", "page_footer", "page_number", "watermark"}
    _excluded_content_layers = {"furniture"}

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def is_enabled(
        self,
        *,
        chunking_enabled: bool | None = None,
    ) -> bool:
        return self._settings.chunking_enabled if chunking_enabled is None else chunking_enabled

    def strategy(
        self,
        *,
        chunking_strategy: str | None = None,
    ) -> str:
        return validate_chunking_strategy(chunking_strategy or self._settings.chunking_strategy)

    def chunk(
        self,
        document: ParsedDocument,
        *,
        chunking_document: Any | None = None,
        chunking_enabled: bool | None = None,
        chunking_strategy: str | None = None,
    ) -> list[DocumentChunk]:
        if not self.is_enabled(chunking_enabled=chunking_enabled):
            return []

        strategy = self.strategy(chunking_strategy=chunking_strategy)
        if strategy in {"hybrid", "line_based"} and chunking_document is not None:
            try:
                return self._docling_chunks(
                    document,
                    docling_document=chunking_document,
                    strategy=strategy,
                    settings=self._settings,
                )
            except Exception:
                if strategy != "legacy_char":
                    return self._legacy_chunks(document, strategy="legacy_char_fallback")

        return self._legacy_chunks(document, strategy=strategy)

    def _docling_chunks(
        self,
        document: ParsedDocument,
        *,
        docling_document: Any,
        strategy: str,
        settings: Settings,
    ) -> list[DocumentChunk]:
        chunker = self._build_docling_chunker(strategy, settings)
        chunks: list[DocumentChunk] = []
        document_metadata = document.metadata.get("docling", {})
        for index, chunk in enumerate(chunker.chunk(dl_doc=docling_document)):
            raw_text = str(getattr(chunk, "text", "") or "").strip()
            if not raw_text:
                continue
            text = str(chunker.contextualize(chunk=chunk) or raw_text).strip()
            metadata = self._docling_chunk_metadata(chunk)
            chunks.append(
                DocumentChunk(
                    chunk_id=f"{document.document_id}:{len(chunks) + 1}",
                    document_id=document.document_id,
                    page_start=metadata["page_start"],
                    page_end=metadata["page_end"],
                    text=text,
                    metadata={
                        "source_file_name": document.source_file_name,
                        "parser": document_metadata.get("parser", "docling"),
                        "input_format": document_metadata.get("input_format"),
                        "pipeline": document_metadata.get("pipeline"),
                        "chunker_strategy": strategy,
                        "contextualized": text != raw_text,
                        "raw_text": raw_text,
                        "chunk_index": index,
                        "tokenizer_model": settings.chunk_tokenizer_model,
                        "max_tokens": settings.chunk_max_tokens,
                        **metadata,
                    },
                )
            )
        return chunks

    @staticmethod
    def _build_docling_chunker(strategy: str, settings: Settings) -> Any:
        tokenizer = _WhitespaceTokenizer(max_tokens=settings.chunk_max_tokens)
        if strategy == "line_based":
            from docling_core.transforms.chunker.line_chunker import LineBasedTokenChunker

            return LineBasedTokenChunker(
                tokenizer=tokenizer,
                omit_prefix_on_overflow=settings.chunk_omit_prefix_on_overflow,
            )

        from docling.chunking import HybridChunker

        return HybridChunker(
            tokenizer=tokenizer,
            merge_peers=settings.chunk_merge_peers,
            repeat_table_header=settings.chunk_repeat_table_header,
            omit_header_on_overflow=settings.chunk_omit_header_on_overflow,
        )

    @staticmethod
    def _docling_chunk_metadata(chunk: Any) -> dict[str, Any]:
        meta = getattr(chunk, "meta", None)
        headings = list(getattr(meta, "headings", None) or [])
        captions = list(getattr(meta, "captions", None) or [])
        doc_items = list(getattr(meta, "doc_items", None) or [])
        element_ids = []
        element_types = []
        pages = []
        provenance = []
        for item in doc_items:
            self_ref = getattr(item, "self_ref", None)
            if self_ref:
                element_ids.append(str(self_ref))
            label = getattr(item, "label", None)
            if label is not None:
                element_types.append(str(getattr(label, "value", label)))
            for prov in getattr(item, "prov", []) or []:
                page_no = getattr(prov, "page_no", None)
                if page_no is not None:
                    pages.append(int(page_no))
                provenance.append(_dump_value(prov))

        return {
            "headings": headings,
            "captions": captions,
            "element_ids": element_ids,
            "element_types": element_types,
            "page_start": min(pages) if pages else None,
            "page_end": max(pages) if pages else None,
            "provenance": provenance,
        }

    def _legacy_chunks(self, document: ParsedDocument, *, strategy: str) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        docling_metadata = document.metadata.get("docling", {})
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
                            "parser": document.metadata.get("docling_options", {})
                            .get("common", {})
                            .get("parser", "docling"),
                            "input_format": docling_metadata.get("input_format"),
                            "pipeline": docling_metadata.get("pipeline"),
                            "chunker_strategy": strategy,
                            "contextualized": False,
                            "raw_text": chunk_text,
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


def _dump_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


class _WhitespaceTokenizer(BaseTokenizer):
    max_tokens: int

    def count_tokens(self, text: str) -> int:
        return len(text.split())

    def get_max_tokens(self) -> int:
        return self.max_tokens

    def get_tokenizer(self) -> _WhitespaceTokenizer:
        return self
