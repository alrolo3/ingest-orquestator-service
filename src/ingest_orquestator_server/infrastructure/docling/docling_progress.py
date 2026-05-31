from __future__ import annotations

import contextvars
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import Event, Lock, Thread
from time import monotonic
from typing import Any

from ingest_orquestator_server.models.parse_progress import (
    ParseProgressCallback,
    ParseProgressUpdate,
)

_CURRENT_CONTEXT: contextvars.ContextVar[DoclingProgressContext | None] = (
    contextvars.ContextVar("docling_progress_context", default=None)
)


class DoclingProgressContext:
    def __init__(
        self,
        *,
        callback: ParseProgressCallback,
        input_format: str,
        pipeline: str,
        page_count: int | None,
        heartbeat_interval_seconds: float,
        page_log_interval: int,
    ) -> None:
        self._callback = callback
        self._input_format = input_format
        self._pipeline = pipeline
        self._page_count = page_count
        self._heartbeat_interval_seconds = heartbeat_interval_seconds
        self._page_log_interval = page_log_interval
        self._started = monotonic()
        self._last_stage = "docling.convert.pending"
        self._last_message = "Docling conversion is queued."
        self._last_reported_completed = 0
        self._completed_pages: set[int] = set()
        self._lock = Lock()
        self._stop_event = Event()
        self._heartbeat_thread: Thread | None = None

    @property
    def page_count(self) -> int | None:
        with self._lock:
            return self._page_count

    @property
    def pages_completed(self) -> int:
        with self._lock:
            return len(self._completed_pages)

    def start(self) -> None:
        if self._heartbeat_interval_seconds <= 0:
            return
        self._heartbeat_thread = Thread(
            target=self._heartbeat_loop,
            name="docling-progress-heartbeat",
            daemon=True,
        )
        self._heartbeat_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=1)

    def set_page_count(self, page_count: int | None) -> None:
        if page_count is None:
            return
        with self._lock:
            self._page_count = page_count

    def report(
        self,
        *,
        stage: str,
        component: str = "docling",
        message: str | None = None,
        page_count: int | None = None,
        pages_completed: int | None = None,
        current_page: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        if page_count is not None:
            self.set_page_count(page_count)
        with self._lock:
            resolved_page_count = self._page_count
            resolved_completed = (
                len(self._completed_pages)
                if pages_completed is None
                else pages_completed
            )
            self._last_stage = stage
            if message:
                self._last_message = message

        self._callback(
            ParseProgressUpdate(
                component=component,
                stage=stage,
                message=message,
                input_format=self._input_format,
                pipeline=self._pipeline,
                page_count=resolved_page_count,
                pages_completed=resolved_completed,
                current_page=current_page,
                details=details,
            )
        )

    def mark_page_completed(
        self,
        page_no: int,
        *,
        stage: str,
        component: str,
    ) -> None:
        should_report = False
        with self._lock:
            self._completed_pages.add(page_no)
            completed = len(self._completed_pages)
            page_count = self._page_count
            self._last_stage = stage
            self._last_message = "Docling page processing completed."
            if completed == page_count:
                should_report = True
            elif completed - self._last_reported_completed >= self._page_log_interval:
                should_report = True
            if should_report:
                self._last_reported_completed = completed

        if should_report:
            self.report(
                component=component,
                stage=stage,
                message="Docling page processing completed.",
                pages_completed=completed,
                current_page=page_no,
            )

    def _heartbeat_loop(self) -> None:
        while not self._stop_event.wait(self._heartbeat_interval_seconds):
            with self._lock:
                elapsed_seconds = round(monotonic() - self._started, 2)
                stage = self._last_stage
                message = self._last_message
                page_count = self._page_count
                pages_completed = len(self._completed_pages)
            self._callback(
                ParseProgressUpdate(
                    component="docling",
                    stage=stage,
                    message=message,
                    input_format=self._input_format,
                    pipeline=self._pipeline,
                    page_count=page_count,
                    pages_completed=pages_completed,
                    details={"elapsed_seconds": elapsed_seconds, "heartbeat": True},
                )
            )


@contextmanager
def docling_progress_context(
    *,
    callback: ParseProgressCallback | None,
    input_format: str,
    pipeline: str,
    page_count: int | None,
    heartbeat_interval_seconds: float,
    page_log_interval: int,
) -> Iterator[DoclingProgressContext | None]:
    if callback is None:
        yield None
        return

    context = DoclingProgressContext(
        callback=callback,
        input_format=input_format,
        pipeline=pipeline,
        page_count=page_count,
        heartbeat_interval_seconds=heartbeat_interval_seconds,
        page_log_interval=page_log_interval,
    )
    token = _CURRENT_CONTEXT.set(context)
    context.start()
    try:
        yield context
    finally:
        context.stop()
        _CURRENT_CONTEXT.reset(token)


def current_docling_progress_context() -> DoclingProgressContext | None:
    return _CURRENT_CONTEXT.get()


def estimate_source_page_count(source_path: Path, input_format: str) -> int | None:
    if input_format == "image":
        return 1
    if input_format != "pdf":
        return None
    try:
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(str(source_path))
        try:
            return len(pdf)
        finally:
            close = getattr(pdf, "close", None)
            if close is not None:
                close()
    except Exception:
        return None


def progress_model_names(models: list[Any]) -> list[str]:
    names: list[str] = []
    for model in models:
        enabled = getattr(model, "enabled", None)
        if enabled is False:
            continue
        names.append(type(model).__name__)
    return names
