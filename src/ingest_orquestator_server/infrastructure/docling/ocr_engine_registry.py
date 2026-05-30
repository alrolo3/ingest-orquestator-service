from __future__ import annotations

from typing import Any


class OcrEngineRegistry:
    def __init__(self, *, allow_external_plugins: bool) -> None:
        self._allow_external_plugins = allow_external_plugins

    def create_options(self, kind: str) -> Any:
        factory = self._factory()
        try:
            return factory.create_options(kind=kind)
        except Exception as exc:
            available = ", ".join(self.available_engines()) or "<none>"
            raise RuntimeError(
                f"Docling OCR engine {kind!r} is not available. "
                f"Available engines: {available}. "
                "For custom OCR, install a Docling plugin that exposes the "
                "`docling` entry point and an `ocr_engines()` factory."
            ) from exc

    def available_engines(self) -> list[str]:
        factory = self._factory()
        return sorted(str(kind) for kind in factory.registered_kind)

    def _factory(self) -> Any:
        from docling.models.factories import get_ocr_factory

        return get_ocr_factory(allow_external_plugins=self._allow_external_plugins)
