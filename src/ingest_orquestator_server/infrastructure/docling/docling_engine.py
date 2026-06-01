from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock, Semaphore
from typing import Any, Protocol

from ingest_orquestator_server.application.services.stage_logger import log_stage
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.docling.docling_converter_factory import (
    DoclingConverterFactory,
)
from ingest_orquestator_server.infrastructure.docling.docling_formats import (
    validate_allowed_format,
)
from ingest_orquestator_server.infrastructure.docling.docling_options import (
    docling_options_metadata,
)


class DoclingConverterFactoryProtocol(Protocol):
    def create(
        self,
        settings: Settings,
        *,
        pipeline: str = "standard",
        input_format: str | None = None,
    ) -> Any: ...


@dataclass(frozen=True)
class DoclingEngineKey:
    input_format: str
    pipeline: str
    signature: str

    @property
    def short_signature(self) -> str:
        return self.signature[:12]

    @property
    def label(self) -> str:
        return f"{self.input_format}:{self.pipeline}:{self.short_signature}"


@dataclass
class DoclingEngine:
    key: DoclingEngineKey
    converter: Any
    concurrency: int
    cache_enabled: bool
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    initialized_formats: set[str] = field(default_factory=set)
    initialize_count: int = 0
    conversion_count: int = 0
    batch_conversion_count: int = 0
    cache_hit_count: int = 0
    last_used_at: datetime | None = None
    last_initialize_ms: int | None = None
    last_conversion_ms: int | None = None
    last_batch_size: int | None = None
    last_cuda_memory: dict[str, Any] | None = None
    _lock: Lock = field(default_factory=Lock, repr=False)
    _semaphore: Semaphore = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._semaphore = Semaphore(self.concurrency)

    def initialize(self, input_format: str) -> None:
        with self._lock:
            if input_format in self.initialized_formats:
                self.cache_hit_count += 1
                return
            started = time.perf_counter()
            log_stage(
                "docling.engine.initialize.started",
                engine_key=self.key.label,
                input_format=input_format,
                pipeline=self.key.pipeline,
            )
            initialize_pipeline = getattr(self.converter, "initialize_pipeline", None)
            if initialize_pipeline is not None:
                initialize_pipeline(_docling_input_format(input_format))
            self.initialized_formats.add(input_format)
            self.initialize_count += 1
            self.last_initialize_ms = round((time.perf_counter() - started) * 1000)
            self.last_cuda_memory = _cuda_memory_snapshot()
            log_stage(
                "docling.engine.initialize.completed",
                engine_key=self.key.label,
                input_format=input_format,
                pipeline=self.key.pipeline,
                duration_ms=self.last_initialize_ms,
                cuda_memory=self.last_cuda_memory,
            )

    def convert(self, source_path: Path, *, input_format: str) -> Any:
        with self._semaphore:
            self.initialize(input_format)
            started = time.perf_counter()
            self.last_used_at = datetime.now(UTC)
            log_stage(
                "docling.engine.convert.started",
                engine_key=self.key.label,
                input_format=input_format,
                pipeline=self.key.pipeline,
                source_path=source_path,
            )
            result = self.converter.convert(source_path)
            self.conversion_count += 1
            self.last_conversion_ms = round((time.perf_counter() - started) * 1000)
            self.last_cuda_memory = _cuda_memory_snapshot()
            log_stage(
                "docling.engine.convert.completed",
                engine_key=self.key.label,
                input_format=input_format,
                pipeline=self.key.pipeline,
                source_path=source_path,
                duration_ms=self.last_conversion_ms,
                cuda_memory=self.last_cuda_memory,
            )
            return result

    def convert_all(self, source_paths: list[Path], *, input_format: str) -> list[Any]:
        with self._semaphore:
            self.initialize(input_format)
            started = time.perf_counter()
            self.last_used_at = datetime.now(UTC)
            self.last_batch_size = len(source_paths)
            log_stage(
                "docling.engine.batch_convert.started",
                engine_key=self.key.label,
                input_format=input_format,
                pipeline=self.key.pipeline,
                batch_size=len(source_paths),
            )
            results = list(self.converter.convert_all(source_paths, raises_on_error=False))
            self.batch_conversion_count += 1
            self.conversion_count += len(source_paths)
            self.last_conversion_ms = round((time.perf_counter() - started) * 1000)
            self.last_cuda_memory = _cuda_memory_snapshot()
            log_stage(
                "docling.engine.batch_convert.completed",
                engine_key=self.key.label,
                input_format=input_format,
                pipeline=self.key.pipeline,
                batch_size=len(source_paths),
                duration_ms=self.last_conversion_ms,
                cuda_memory=self.last_cuda_memory,
            )
            return results

    def snapshot(self) -> dict[str, Any]:
        return {
            "engine_key": self.key.label,
            "input_format": self.key.input_format,
            "pipeline": self.key.pipeline,
            "signature": self.key.signature,
            "cache_enabled": self.cache_enabled,
            "concurrency": self.concurrency,
            "created_at": self.created_at.isoformat(),
            "initialized_formats": sorted(self.initialized_formats),
            "initialize_count": self.initialize_count,
            "conversion_count": self.conversion_count,
            "batch_conversion_count": self.batch_conversion_count,
            "cache_hit_count": self.cache_hit_count,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "last_initialize_ms": self.last_initialize_ms,
            "last_conversion_ms": self.last_conversion_ms,
            "last_batch_size": self.last_batch_size,
            "last_cuda_memory": self.last_cuda_memory,
        }


class DoclingEngineRegistry:
    def __init__(
        self,
        *,
        settings: Settings,
        converter_factory: DoclingConverterFactoryProtocol | None = None,
    ) -> None:
        self._settings = settings
        self._converter_factory = converter_factory or DoclingConverterFactory()
        self._engines: dict[DoclingEngineKey, list[DoclingEngine]] = {}
        self._leased_engine_ids: set[int] = set()
        self._lock = Lock()
        self._parse_semaphore = Semaphore(settings.effective_docling_parse_concurrency)

    def acquire_engine(
        self,
        *,
        settings: Settings | None = None,
        input_format: str,
        pipeline: str,
    ) -> DoclingEngine:
        effective_settings = settings or self._settings
        validate_allowed_format(input_format, effective_settings.docling_allowed_formats)
        key = build_docling_engine_key(
            effective_settings,
            input_format=input_format,
            pipeline=pipeline,
        )
        self._parse_semaphore.acquire()
        try:
            if not effective_settings.docling_engine_cache_enabled:
                return self._build_engine(key, settings=effective_settings, cache_hit=False)

            with self._lock:
                for engine in self._engines.get(key, []):
                    if id(engine) in self._leased_engine_ids:
                        continue
                    self._leased_engine_ids.add(id(engine))
                    engine.cache_hit_count += 1
                    log_stage(
                        "docling.engine.cache.hit",
                        engine_key=key.label,
                        input_format=input_format,
                        pipeline=pipeline,
                        initialized_formats=sorted(engine.initialized_formats),
                    )
                    return engine

                engine = self._build_engine(
                    key,
                    settings=effective_settings,
                    cache_hit=False,
                )
                self._engines.setdefault(key, []).append(engine)
                self._leased_engine_ids.add(id(engine))
                return engine
        except Exception:
            self._parse_semaphore.release()
            raise

    def release_engine(self, engine: DoclingEngine, *, discard: bool = False) -> None:
        try:
            with self._lock:
                self._leased_engine_ids.discard(id(engine))
                if discard or not engine.cache_enabled:
                    engines = self._engines.get(engine.key)
                    if engines is not None:
                        self._engines[engine.key] = [
                            cached_engine
                            for cached_engine in engines
                            if cached_engine is not engine
                        ]
                        if not self._engines[engine.key]:
                            del self._engines[engine.key]
                    if discard:
                        log_stage(
                            "docling.engine.discarded",
                            engine_key=engine.key.label,
                            input_format=engine.key.input_format,
                            pipeline=engine.key.pipeline,
                        )
        finally:
            self._parse_semaphore.release()

    def evict_idle(self) -> int:
        ttl_seconds = self._settings.docling_engine_idle_ttl_seconds
        if ttl_seconds <= 0:
            return 0

        now = datetime.now(UTC)
        evicted = 0
        with self._lock:
            for key, engines in list(self._engines.items()):
                retained: list[DoclingEngine] = []
                for engine in engines:
                    if id(engine) in self._leased_engine_ids:
                        retained.append(engine)
                        continue
                    idle_since = engine.last_used_at or engine.created_at
                    if (now - idle_since).total_seconds() <= ttl_seconds:
                        retained.append(engine)
                        continue
                    evicted += 1
                    log_stage(
                        "docling.engine.evicted",
                        engine_key=key.label,
                        input_format=key.input_format,
                        pipeline=key.pipeline,
                        idle_ttl_seconds=ttl_seconds,
                    )
                if retained:
                    self._engines[key] = retained
                else:
                    del self._engines[key]
        return evicted

    def warmup(self, *, formats: Iterable[str] | None = None) -> None:
        warmup_formats = list(formats or self._settings.docling_engine_warmup_formats)
        for input_format in warmup_formats:
            if input_format not in self._settings.docling_allowed_formats:
                log_stage(
                    "docling.engine.warmup.skipped",
                    input_format=input_format,
                    reason="format_not_allowed",
                )
                continue
            engine = self.acquire_engine(
                input_format=input_format,
                pipeline=self._settings.docling_pipeline,
            )
            try:
                engine.initialize(input_format)
            except Exception:
                self.release_engine(engine, discard=True)
                raise
            self.release_engine(engine)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            engines = [
                engine.snapshot()
                for engine_pool in self._engines.values()
                for engine in engine_pool
            ]
            leased_engine_count = len(self._leased_engine_ids)
        return {
            "cache_enabled": self._settings.docling_engine_cache_enabled,
            "warmup_enabled": self._settings.docling_engine_warmup_enabled,
            "warmup_formats": self._settings.docling_engine_warmup_formats,
            "parse_concurrency": self._settings.effective_docling_parse_concurrency,
            "leased_engine_count": leased_engine_count,
            "engine_idle_ttl_seconds": self._settings.docling_engine_idle_ttl_seconds,
            "perf_page_batch_size": self._settings.docling_perf_page_batch_size,
            "engine_count": len(engines),
            "engines": engines,
        }

    def _build_engine(
        self,
        key: DoclingEngineKey,
        *,
        settings: Settings,
        cache_hit: bool,
    ) -> DoclingEngine:
        started = time.perf_counter()
        log_stage(
            "docling.engine.cache.miss",
            engine_key=key.label,
            input_format=key.input_format,
            pipeline=key.pipeline,
            cache_enabled=self._settings.docling_engine_cache_enabled,
            cache_hit=cache_hit,
        )
        converter = self._converter_factory.create(
            settings,
            pipeline=key.pipeline,
            input_format=key.input_format,
        )
        engine = DoclingEngine(
            key=key,
            converter=converter,
            concurrency=1,
            cache_enabled=settings.docling_engine_cache_enabled,
        )
        log_stage(
            "docling.engine.created",
            engine_key=key.label,
            input_format=key.input_format,
            pipeline=key.pipeline,
            duration_ms=round((time.perf_counter() - started) * 1000),
            parse_concurrency=settings.effective_docling_parse_concurrency,
            converter_concurrency=1,
        )
        return engine


class DoclingConversionScheduler:
    def __init__(self, *, engine_registry: DoclingEngineRegistry) -> None:
        self._engine_registry = engine_registry

    def convert(
        self,
        source_path: Path,
        *,
        settings: Settings | None = None,
        input_format: str,
        pipeline: str,
    ) -> tuple[Any, dict[str, Any]]:
        self._engine_registry.evict_idle()
        engine = self._engine_registry.acquire_engine(
            settings=settings,
            input_format=input_format,
            pipeline=pipeline,
        )
        discard_engine = True
        try:
            result = engine.convert(source_path, input_format=input_format)
            snapshot = engine.snapshot()
            discard_engine = False
            return result, snapshot
        finally:
            self._engine_registry.release_engine(engine, discard=discard_engine)

    def convert_all(
        self,
        source_paths: list[Path],
        *,
        settings: Settings | None = None,
        input_format: str,
        pipeline: str,
    ) -> tuple[list[Any], dict[str, Any]]:
        self._engine_registry.evict_idle()
        engine = self._engine_registry.acquire_engine(
            settings=settings,
            input_format=input_format,
            pipeline=pipeline,
        )
        discard_engine = True
        try:
            results = engine.convert_all(source_paths, input_format=input_format)
            snapshot = engine.snapshot()
            discard_engine = False
            return results, snapshot
        finally:
            self._engine_registry.release_engine(engine, discard=discard_engine)

    def snapshot(self) -> dict[str, Any]:
        return self._engine_registry.snapshot()


def build_docling_engine_key(
    settings: Settings,
    *,
    input_format: str,
    pipeline: str,
) -> DoclingEngineKey:
    payload = {
        "input_format": input_format,
        "pipeline": pipeline,
        "options": docling_options_metadata(
            settings,
            input_format=input_format,
            pipeline=pipeline,
        ),
        "engine": {
            "cache_enabled": settings.docling_engine_cache_enabled,
            "parse_concurrency": settings.effective_docling_parse_concurrency,
            "perf_page_batch_size": settings.docling_perf_page_batch_size,
        },
    }
    serialized = json.dumps(payload, sort_keys=True, default=str)
    return DoclingEngineKey(
        input_format=input_format,
        pipeline=pipeline,
        signature=hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
    )



def _docling_input_format(input_format: str) -> Any:
    from docling.datamodel.base_models import InputFormat

    return InputFormat(input_format)


def _cuda_memory_snapshot() -> dict[str, Any] | None:
    try:
        import torch
    except Exception:
        return None

    try:
        if not torch.cuda.is_available():
            return None
        return {
            "allocated_gb": round(torch.cuda.memory_allocated() / 1024**3, 3),
            "reserved_gb": round(torch.cuda.memory_reserved() / 1024**3, 3),
            "max_allocated_gb": round(torch.cuda.max_memory_allocated() / 1024**3, 3),
            "device": torch.cuda.get_device_name(0),
        }
    except Exception:
        return None
