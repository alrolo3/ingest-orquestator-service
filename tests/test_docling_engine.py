from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, Lock
from typing import Any

from ingest_orquestator_server.config import Settings
from ingest_orquestator_server.infrastructure.docling.docling_document_parser import (
    DoclingDocumentParser,
)
from ingest_orquestator_server.infrastructure.docling.docling_engine import (
    DoclingConversionScheduler,
    DoclingEngineRegistry,
)
from ingest_orquestator_server.infrastructure.docling.docling_progress import (
    current_docling_progress_context,
)
from tests.fakes.fake_docling_converter import (
    FakeDoclingConversionResult,
    FakeDoclingConverter,
)


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
        allowed_upload_extensions=[".md"],
    )
    factory = CountingDoclingConverterFactory()
    scheduler = DoclingConversionScheduler(
        engine_registry=DoclingEngineRegistry(
            settings=settings,
            converter_factory=factory,
        ),
    )

    scheduler.convert(input_file, settings=settings, input_format="md", pipeline="standard")
    scheduler.convert(input_file, settings=settings, input_format="md", pipeline="standard")

    assert factory.create_count == 1
    assert factory.converter.initialize_count == 1
    assert factory.converter.convert_count == 2
    snapshot = scheduler.snapshot()
    assert snapshot["engine_count"] == 1
    assert snapshot["engines"][0]["cache_hit_count"] >= 1
    assert snapshot["engines"][0]["initialized_formats"] == ["md"]


def test_docling_conversion_scheduler_does_not_batch_independent_conversions(
    tmp_path: Path,
) -> None:
    files = [
        _write_markdown(tmp_path / "one.md"),
        _write_markdown(tmp_path / "two.md"),
    ]
    settings = Settings(
        allowed_upload_extensions=[".md"],
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
                settings=settings,
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
    assert factory.create_count >= 1
    assert factory.converter.convert_all_count == 0
    assert factory.converter.convert_count == 2


def test_docling_scheduler_allows_conversions_up_to_parse_concurrency(
    tmp_path: Path,
) -> None:
    files = [
        _write_markdown(tmp_path / "one.md"),
        _write_markdown(tmp_path / "two.md"),
    ]
    controller = ControlledConversionController()
    settings = Settings(
        allowed_upload_extensions=[".md"],
        parser_worker_count=2,
    )
    scheduler = DoclingConversionScheduler(
        engine_registry=DoclingEngineRegistry(
            settings=settings,
            converter_factory=ControlledDoclingConverterFactory(controller),
        ),
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                scheduler.convert,
                file_path,
                settings=settings,
                input_format="md",
                pipeline="standard",
            )
            for file_path in files
        ]
        assert controller.wait_for_started(2)
        controller.release()
        results = [future.result(timeout=5) for future in futures]

    assert [result.document.source_path.name for result, _metadata in results] == [
        "one.md",
        "two.md",
    ]
    assert controller.max_active == 2


def test_docling_scheduler_bounds_conversions_to_parse_concurrency(
    tmp_path: Path,
) -> None:
    files = [
        _write_markdown(tmp_path / "one.md"),
        _write_markdown(tmp_path / "two.md"),
        _write_markdown(tmp_path / "three.md"),
    ]
    controller = ControlledConversionController()
    settings = Settings(
        allowed_upload_extensions=[".md"],
        parser_worker_count=1,
    )
    scheduler = DoclingConversionScheduler(
        engine_registry=DoclingEngineRegistry(
            settings=settings,
            converter_factory=ControlledDoclingConverterFactory(controller),
        ),
    )

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(
                scheduler.convert,
                file_path,
                settings=settings,
                input_format="md",
                pipeline="standard",
            )
            for file_path in files
        ]
        assert controller.wait_for_started(1)
        assert not controller.wait_for_started(2, timeout=0.1)
        controller.release()
        results = [future.result(timeout=5) for future in futures]

    assert sorted(result.document.source_path.name for result, _metadata in results) == [
        "one.md",
        "three.md",
        "two.md",
    ]
    assert controller.max_active == 1


def test_docling_parser_progress_callbacks_are_isolated_for_concurrent_jobs(
    tmp_path: Path,
) -> None:
    first = _write_markdown(tmp_path / "first.md")
    second = _write_markdown(tmp_path / "second.md")
    controller = ControlledConversionController()
    settings = Settings(
        allowed_upload_extensions=[".md"],
        parser_worker_count=2,
        progress_log_interval_seconds=0,
    )
    scheduler = DoclingConversionScheduler(
        engine_registry=DoclingEngineRegistry(
            settings=settings,
            converter_factory=ControlledDoclingConverterFactory(
                controller,
                report_progress=True,
            ),
        ),
    )
    parser = DoclingDocumentParser(settings=settings, conversion_scheduler=scheduler)
    updates_by_file: dict[str, list[dict[str, Any]]] = {"first.md": [], "second.md": []}

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                parser.parse,
                file_path,
                progress_callback=lambda update, file_name=file_path.name: (
                    updates_by_file[file_name].append(
                        {
                            "stage": update.stage,
                            "details": update.details,
                            "pages_completed": update.pages_completed,
                        }
                    )
                ),
            )
            for file_path in [first, second]
        ]
        assert controller.wait_for_started(2)
        controller.release()
        for future in futures:
            future.result(timeout=5)

    assert _progress_sources(updates_by_file["first.md"]) == {"first.md"}
    assert _progress_sources(updates_by_file["second.md"]) == {"second.md"}


def test_docling_scheduler_failed_conversion_does_not_poison_active_conversions(
    tmp_path: Path,
) -> None:
    good_file = _write_markdown(tmp_path / "good.md")
    failed_file = _write_markdown(tmp_path / "failed.md")
    controller = ControlledConversionController(fail_names={"failed.md"})
    settings = Settings(
        allowed_upload_extensions=[".md"],
        parser_worker_count=2,
    )
    scheduler = DoclingConversionScheduler(
        engine_registry=DoclingEngineRegistry(
            settings=settings,
            converter_factory=ControlledDoclingConverterFactory(controller),
        ),
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        good_future = executor.submit(
            scheduler.convert,
            good_file,
            settings=settings,
            input_format="md",
            pipeline="standard",
        )
        failed_future = executor.submit(
            scheduler.convert,
            failed_file,
            settings=settings,
            input_format="md",
            pipeline="standard",
        )
        assert controller.wait_for_started(2)
        controller.release()

        result, _metadata = good_future.result(timeout=5)
        assert result.document.source_path.name == "good.md"
        try:
            failed_future.result(timeout=5)
        except RuntimeError as exc:
            assert str(exc) == "conversion failed for failed.md"
        else:
            raise AssertionError("failed conversion should raise")


def test_docling_parser_records_engine_metadata_when_scheduler_is_used(
    tmp_path: Path,
) -> None:
    input_file = _write_markdown(tmp_path / "example.md")
    settings = Settings(
        allowed_upload_extensions=[".md"],
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
        allowed_upload_extensions=[".md"],
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


class ControlledConversionController:
    def __init__(self, *, fail_names: set[str] | None = None) -> None:
        self.fail_names = fail_names or set()
        self.started_names: list[str] = []
        self.active = 0
        self.max_active = 0
        self._lock = Lock()
        self._started_event = Event()
        self._release_event = Event()

    def enter(self, source_path: Path) -> None:
        with self._lock:
            self.started_names.append(source_path.name)
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            self._started_event.set()

    def exit(self) -> None:
        with self._lock:
            self.active -= 1
            self._started_event.set()

    def wait_for_started(self, count: int, *, timeout: float = 2.0) -> bool:
        deadline = timeout
        while deadline > 0:
            with self._lock:
                if len(self.started_names) >= count:
                    return True
            self._started_event.wait(min(0.01, deadline))
            self._started_event.clear()
            deadline -= 0.01
        with self._lock:
            return len(self.started_names) >= count

    def release(self) -> None:
        self._release_event.set()

    def wait_until_released(self) -> None:
        if not self._release_event.wait(timeout=5):
            raise TimeoutError("conversion was not released by the test")


class ControlledDoclingConverterFactory:
    def __init__(
        self,
        controller: ControlledConversionController,
        *,
        report_progress: bool = False,
    ) -> None:
        self._controller = controller
        self._report_progress = report_progress

    def create(
        self,
        settings: Settings,
        *,
        pipeline: str = "standard",
        input_format: str | None = None,
    ) -> Any:
        _ = settings, pipeline, input_format
        return ControlledDoclingConverter(
            self._controller,
            report_progress=self._report_progress,
        )


class ControlledDoclingConverter(FakeDoclingConverter):
    def __init__(
        self,
        controller: ControlledConversionController,
        *,
        report_progress: bool,
    ) -> None:
        super().__init__()
        self._controller = controller
        self._report_progress = report_progress

    def convert(self, source_path: Path) -> object:
        self._controller.enter(source_path)
        try:
            if source_path.name in self._controller.fail_names:
                raise RuntimeError(f"conversion failed for {source_path.name}")
            if self._report_progress:
                context = current_docling_progress_context()
                if context is not None:
                    context.report(
                        stage="docling.test.page.completed",
                        component="docling.test",
                        message="Test page completed.",
                        page_count=1,
                        pages_completed=1,
                        current_page=1,
                        details={"source_file_name": source_path.name},
                    )
            self._controller.wait_until_released()
            self.convert_count += 1
            return FakeDoclingConversionResult(source_path)
        finally:
            self._controller.exit()


def _progress_sources(updates: list[dict[str, Any]]) -> set[str]:
    return {
        str(update["details"]["source_file_name"])
        for update in updates
        if update["stage"] == "docling.test.page.completed"
    }
