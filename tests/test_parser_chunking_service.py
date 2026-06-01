from pathlib import Path
from typing import Any

import pytest
from docling_core.transforms.chunker.tokenizer.base import BaseTokenizer

from ingest_orquestator_server.application.exceptions import UnsupportedIngestionOptionError
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.docling import docling_chunker
from ingest_orquestator_server.infrastructure.docling.docling_chunker import (
    DoclingParserChunker,
    load_huggingface_tokenizer,
)
from ingest_orquestator_server.models.chunking import ChunkingStrategy
from ingest_orquestator_server.models.parsed_document import ParsedDocument


class WhitespaceTokenizer(BaseTokenizer):
    def __init__(self, max_tokens: int) -> None:
        self._max_tokens = max_tokens

    def count_tokens(self, text: str) -> int:
        return len(text.split())

    def get_max_tokens(self) -> int:
        return self._max_tokens

    def get_tokenizer(self) -> object:
        return self


def test_docling_chunking_capabilities_expose_token_and_page(tmp_path: Path) -> None:
    chunker = DoclingParserChunker(Settings(storage_dir=tmp_path))

    capabilities = chunker.capabilities()

    assert [strategy.value for strategy in capabilities.strategies] == [
        ChunkingStrategy.TOKEN,
        ChunkingStrategy.PAGE,
    ]
    assert capabilities.default_strategy == ChunkingStrategy.PAGE


def test_docling_chunking_rejects_line_strategy(tmp_path: Path) -> None:
    chunker = DoclingParserChunker(Settings(storage_dir=tmp_path))

    with pytest.raises(UnsupportedIngestionOptionError, match="does not support.*line"):
        chunker.validate_strategy(ChunkingStrategy.LINE)


def test_docling_page_strategy_uses_hierarchical_chunker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    class FakeDoclingChunk:
        text = "page chunk"
        meta = None

    class RecordingHierarchicalChunker:
        def __init__(self) -> None:
            calls.append("init")

        def chunk(self, *, dl_doc: Any) -> list[FakeDoclingChunk]:
            calls.append(f"chunk:{dl_doc}")
            return [FakeDoclingChunk()]

        def contextualize(self, *, chunk: FakeDoclingChunk) -> str:
            calls.append("contextualize")
            return chunk.text

    monkeypatch.setattr(docling_chunker, "HierarchicalChunker", RecordingHierarchicalChunker)

    chunks = DoclingParserChunker(Settings(storage_dir=tmp_path)).chunk(
        ParsedDocument(
            document_id="doc-1",
            source_file_name="example.md",
            source_path="/tmp/example.md",
            metadata={"docling": {"parser": "docling", "input_format": "md"}},
        ),
        chunking_document="native-docling-document",
        strategy=ChunkingStrategy.PAGE,
    )

    assert calls == ["init", "chunk:native-docling-document", "contextualize"]
    assert chunks[0].text == "page chunk"
    assert chunks[0].metadata["chunking_strategy"] == "page"
    assert chunks[0].metadata["docling_chunker"] == "HierarchicalChunker"


def test_docling_token_strategy_uses_cached_local_huggingface_tokenizer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tokenizer_path = tmp_path / "tokenizer"
    tokenizer_path.mkdir()
    calls: list[tuple[str, dict[str, object]]] = []

    class FakeHuggingFaceTokenizer:
        def __init__(self, *, tokenizer: object, max_tokens: int) -> None:
            self.tokenizer = tokenizer
            self.max_tokens = max_tokens

    def fake_from_pretrained(path: str, **kwargs: object) -> object:
        calls.append((path, kwargs))
        return object()

    load_huggingface_tokenizer.cache_clear()
    monkeypatch.setattr(
        docling_chunker.AutoTokenizer,
        "from_pretrained",
        fake_from_pretrained,
    )
    monkeypatch.setattr(docling_chunker, "HuggingFaceTokenizer", FakeHuggingFaceTokenizer)

    first = load_huggingface_tokenizer(str(tokenizer_path), 256)
    second = load_huggingface_tokenizer(str(tokenizer_path), 256)

    assert first is second
    assert calls == [(str(tokenizer_path), {"local_files_only": True})]


def test_docling_token_strategy_requires_local_tokenizer_path(tmp_path: Path) -> None:
    chunker = DoclingParserChunker(Settings(storage_dir=tmp_path))

    with pytest.raises(UnsupportedIngestionOptionError, match="INGEST_CHUNK_TOKENIZER_PATH"):
        chunker.validate_strategy(ChunkingStrategy.TOKEN)


def test_docling_token_strategy_uses_hybrid_chunker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tokenizer_path = tmp_path / "tokenizer"
    tokenizer_path.mkdir()
    calls: list[str] = []

    class FakeDoclingChunk:
        text = "token chunk"
        meta = None

    class RecordingHybridChunker:
        def __init__(self, *, tokenizer: object) -> None:
            assert isinstance(tokenizer, WhitespaceTokenizer)
            calls.append("init")

        def chunk(self, *, dl_doc: Any) -> list[FakeDoclingChunk]:
            calls.append(f"chunk:{dl_doc}")
            return [FakeDoclingChunk()]

        def contextualize(self, *, chunk: FakeDoclingChunk) -> str:
            calls.append("contextualize")
            return chunk.text

    monkeypatch.setattr(docling_chunker, "HybridChunker", RecordingHybridChunker)

    chunks = DoclingParserChunker(
        Settings(storage_dir=tmp_path, chunk_tokenizer_path=tokenizer_path),
        tokenizer_loader=lambda _path, max_tokens: WhitespaceTokenizer(max_tokens),
    ).chunk(
        ParsedDocument(
            document_id="doc-1",
            source_file_name="example.md",
            source_path="/tmp/example.md",
            metadata={"docling": {"parser": "docling", "input_format": "md"}},
        ),
        chunking_document="native-docling-document",
        strategy=ChunkingStrategy.TOKEN,
    )

    assert calls == ["init", "chunk:native-docling-document", "contextualize"]
    assert chunks[0].metadata["chunking_strategy"] == "token"
    assert chunks[0].metadata["docling_chunker"] == "HybridChunker"
