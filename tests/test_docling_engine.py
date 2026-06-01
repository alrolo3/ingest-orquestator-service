from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from ingest_orquestator_server.config import Settings
from ingest_orquestator_server.infrastructure.docling.docling_document_parser import (
    DoclingDocumentParser,
)
from ingest_orquestator_server.infrastructure.docling.docling_engine import (
    DoclingConversionScheduler,
    DoclingEngineRegistry,
)
from tests.fakes.fake_docling_converter import FakeDoclingConverter


class CountingDoclingConverterFactory:
    def __init__(self) -> None:
        self.create_count = 0
        self.converter = FakeDoclingConverter()
        self.ocr_languages: list[list[str]] = []

    def create(
        self,
        settings: Settings,
        *,
        pipeline: str = "standard",
        input_format: str | None = None,
    ) -> Any:
        _ = pipeline, input_format
        self.create_count += 1
        self.ocr_languages.append(list(settings.docling_pdf_ocr_languages))
        return self.converter


def test_docling_engine_registry_reuses_converter_and_initialized_pipeline(
    tmp_path: Path,
) -> None:
    input_file = _write_markdown(tmp_path / "one.md")
    settings = Settings(
        docling_allowed_formats=["md"],
        docling_gpu_batch_wait_ms=0,
    )
    factory = CountingDoclingConverterFactory()
    scheduler = DoclingConversionScheduler(
        engine_registry=DoclingEngineRegistry(
            settings=settings,
            converter_factory=factory,
        ),
    )

    scheduler.convert(input_file, input_format="md", pipeline="standard")
    scheduler.convert(input_file, input_format="md", pipeline="standard")

    assert factory.create_count == 1
    assert factory.converter.initialize_count == 1
    assert factory.converter.convert_count == 2
    snapshot = scheduler.snapshot()
    assert snapshot["engine_count"] == 1
    assert snapshot["engines"][0]["cache_hit_count"] >= 1
    assert snapshot["engines"][0]["initialized_formats"] == ["md"]


def test_docling_conversion_scheduler_batches_concurrent_conversions(
    tmp_path: Path,
) -> None:
    files = [
        _write_markdown(tmp_path / "one.md"),
        _write_markdown(tmp_path / "two.md"),
    ]
    settings = Settings(
        docling_allowed_formats=["md"],
        docling_gpu_batch_max_documents=2,
        docling_gpu_batch_wait_ms=1000,
    )
    factory = CountingDoclingConverterFactory()
    scheduler = DoclingConversionScheduler(
        engine_registry=DoclingEngineRegistry(
            settings=settings,
            converter_factory=factory,
        ),
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                scheduler.convert,
                file_path,
                input_format="md",
                pipeline="standard",
            )
            for file_path in files
        ]
        results = [future.result(timeout=5) for future in futures]

    assert [result.document.source_path.name for result, _metadata in results] == [
        "one.md",
        "two.md",
    ]
    assert factory.create_count == 1
    assert factory.converter.convert_all_count == 1
    assert factory.converter.convert_count == 2


def test_docling_parser_records_engine_metadata_when_scheduler_is_used(
    tmp_path: Path,
) -> None:
    input_file = _write_markdown(tmp_path / "example.md")
    settings = Settings(
        docling_allowed_formats=["md"],
        docling_gpu_batch_wait_ms=0,
    )
    factory = CountingDoclingConverterFactory()
    scheduler = DoclingConversionScheduler(
        engine_registry=DoclingEngineRegistry(
            settings=settings,
            converter_factory=factory,
        ),
    )

    output = DoclingDocumentParser(
        settings=settings,
        conversion_scheduler=scheduler,
    ).parse(input_file)

    assert output.normalized_document is not None
    engine = output.normalized_document.metadata["docling"]["engine"]
    assert engine["engine_key"].startswith("md:standard:")
    assert engine["initialize_count"] == 1
    assert engine["conversion_count"] == 1
    assert output.normalized_document.metadata["docling"]["input_format"] == "md"


def test_docling_engine_registry_reuses_converter_for_same_ocr_languages(
    tmp_path: Path,
) -> None:
    input_file = _write_markdown(tmp_path / "example.md")
    settings = Settings(
        docling_allowed_formats=["md"],
        docling_gpu_batch_wait_ms=0,
    )
    factory = CountingDoclingConverterFactory()
    scheduler = DoclingConversionScheduler(
        engine_registry=DoclingEngineRegistry(
            settings=settings,
            converter_factory=factory,
        ),
    )
    parser = DoclingDocumentParser(settings=settings, conversion_scheduler=scheduler)

    parser.parse(input_file, ocr_languages=["en"])
    parser.parse(input_file, ocr_languages=["en"])
    parser.parse(input_file, ocr_languages=["es"])

    assert factory.create_count == 2
    assert factory.ocr_languages == [["en"], ["es"]]


def _write_markdown(path: Path) -> Path:
    path.write_text("# Example", encoding="utf-8")
    return path
