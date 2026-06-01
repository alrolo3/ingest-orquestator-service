from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

from docling.chunking import HierarchicalChunker, HybridChunker
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from transformers import AutoTokenizer

from ingest_orquestator_server.application.exceptions import UnsupportedIngestionOptionError
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.models.chunking import (
    ChunkingStrategy,
    ChunkingStrategyCapability,
    ParserChunkingCapabilities,
)
from ingest_orquestator_server.models.document_chunk import DocumentChunk
from ingest_orquestator_server.models.parsed_document import ParsedDocument

TokenizerLoader = Callable[[Path, int], Any]


class DoclingParserChunker:
    parser_name = "docling"

    def __init__(
        self,
        settings: Settings,
        *,
        tokenizer_loader: TokenizerLoader | None = None,
    ) -> None:
        self._settings = settings
        self._tokenizer_loader = tokenizer_loader or _load_tokenizer_from_path

    def capabilities(self) -> ParserChunkingCapabilities:
        supported = {ChunkingStrategy.TOKEN, ChunkingStrategy.PAGE}
        configured_default = ChunkingStrategy(self._settings.chunking_strategy)
        default_strategy = (
            configured_default
            if configured_default in supported
            else ChunkingStrategy.PAGE
        )
        return ParserChunkingCapabilities(
            enabled=True,
            default_strategy=default_strategy,
            strategies=[
                ChunkingStrategyCapability(
                    value=ChunkingStrategy.TOKEN,
                    label="Token",
                    default=default_strategy == ChunkingStrategy.TOKEN,
                ),
                ChunkingStrategyCapability(
                    value=ChunkingStrategy.PAGE,
                    label="Page",
                    default=default_strategy == ChunkingStrategy.PAGE,
                ),
            ],
        )

    def validate_strategy(self, strategy: ChunkingStrategy) -> None:
        if strategy == ChunkingStrategy.TOKEN:
            self._tokenizer_path()
            return
        if strategy == ChunkingStrategy.PAGE:
            return
        raise UnsupportedIngestionOptionError(
            f"Parser '{self.parser_name}' does not support chunking strategy '{strategy.value}'"
        )

    def chunk(
        self,
        document: ParsedDocument,
        *,
        chunking_document: Any | None,
        strategy: ChunkingStrategy,
    ) -> list[DocumentChunk]:
        if chunking_document is None:
            raise UnsupportedIngestionOptionError(
                "Docling chunking requires the parser's native DoclingDocument output."
            )
        self.validate_strategy(strategy)
        if strategy == ChunkingStrategy.TOKEN:
            tokenizer = self._tokenizer_loader(
                self._tokenizer_path(),
                self._settings.chunk_max_tokens,
            )
            chunker = HybridChunker(tokenizer=tokenizer)
            docling_chunker_name = "HybridChunker"
        elif strategy == ChunkingStrategy.PAGE:
            chunker = HierarchicalChunker()
            docling_chunker_name = "HierarchicalChunker"
        else:
            raise UnsupportedIngestionOptionError(
                f"Parser '{self.parser_name}' does not support chunking strategy "
                f"'{strategy.value}'"
            )
        return self._docling_chunks(
            document,
            docling_document=chunking_document,
            chunking_strategy=strategy,
            chunker=chunker,
            docling_chunker_name=docling_chunker_name,
        )

    def _tokenizer_path(self) -> Path:
        if self._settings.chunk_tokenizer_path is None:
            raise UnsupportedIngestionOptionError(
                "INGEST_CHUNK_TOKENIZER_PATH must point to a local tokenizer directory "
                "when chunking_strategy=token."
            )
        raw_tokenizer_path = str(self._settings.chunk_tokenizer_path)
        if "://" in raw_tokenizer_path:
            raise UnsupportedIngestionOptionError(
                "INGEST_CHUNK_TOKENIZER_PATH must be a local filesystem path."
            )
        tokenizer_path = Path(raw_tokenizer_path).expanduser()
        if not tokenizer_path.exists() or not tokenizer_path.is_dir():
            raise UnsupportedIngestionOptionError(
                "INGEST_CHUNK_TOKENIZER_PATH must point to an existing local tokenizer "
                "directory."
            )
        return tokenizer_path

    def _docling_chunks(
        self,
        document: ParsedDocument,
        *,
        docling_document: Any,
        chunking_strategy: ChunkingStrategy,
        chunker: Any,
        docling_chunker_name: str,
    ) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        document_metadata = document.metadata.get("docling", {})
        for index, chunk in enumerate(chunker.chunk(dl_doc=docling_document)):
            raw_text = str(getattr(chunk, "text", "") or "").strip()
            if not raw_text:
                continue
            contextualize = getattr(chunker, "contextualize", None)
            if callable(contextualize):
                text = str(contextualize(chunk=chunk) or raw_text).strip()
            else:
                text = raw_text
            metadata = _docling_chunk_metadata(chunk)
            chunks.append(
                DocumentChunk(
                    chunk_id=f"{document.document_id}:{len(chunks) + 1}",
                    document_id=document.document_id,
                    page_start=metadata["page_start"],
                    page_end=metadata["page_end"],
                    text=text,
                    metadata={
                        "source_file_name": document.source_file_name,
                        "parser": document_metadata.get("parser", self.parser_name),
                        "input_format": document_metadata.get("input_format"),
                        "pipeline": document_metadata.get("pipeline"),
                        "chunking_strategy": chunking_strategy.value,
                        "docling_chunker": docling_chunker_name,
                        "contextualized": text != raw_text,
                        "raw_text": raw_text,
                        "chunk_index": index,
                        "max_tokens": self._settings.chunk_max_tokens
                        if chunking_strategy == ChunkingStrategy.TOKEN
                        else None,
                        **metadata,
                    },
                )
            )
        return chunks


@lru_cache(maxsize=4)
def load_huggingface_tokenizer(tokenizer_path: str, max_tokens: int) -> HuggingFaceTokenizer:
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_path, local_files_only=True)
    return HuggingFaceTokenizer(tokenizer=tokenizer, max_tokens=max_tokens)


def _load_tokenizer_from_path(tokenizer_path: Path, max_tokens: int) -> HuggingFaceTokenizer:
    return load_huggingface_tokenizer(str(tokenizer_path), max_tokens)


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


def _dump_value(value: Any) -> Any:
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json")
    if hasattr(value, "__dict__"):
        return {
            key: _dump_value(inner_value)
            for key, inner_value in vars(value).items()
            if not key.startswith("_")
        }
    if isinstance(value, list | tuple):
        return [_dump_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _dump_value(inner_value) for key, inner_value in value.items()}
    return value
