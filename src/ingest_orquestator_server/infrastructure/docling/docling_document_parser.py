from __future__ import annotations

import mimetypes
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from uuid import uuid4

from ingest_orquestator_server.config.profiles import resolve_profile_settings
from ingest_orquestator_server.config.settings import Settings, get_settings
from ingest_orquestator_server.infrastructure.docling.docling_converter_factory import (
    DoclingConverterFactory,
)
from ingest_orquestator_server.infrastructure.docling.docling_formats import (
    detect_input_format,
    resolve_pipeline_mode,
    validate_allowed_format,
)
from ingest_orquestator_server.infrastructure.docling.docling_options import (
    docling_options_metadata,
)
from ingest_orquestator_server.infrastructure.docling.docling_result_metadata import (
    conversion_result_metadata,
)
from ingest_orquestator_server.models.parse_output import ParseOutput
from ingest_orquestator_server.normalizers.docling.docling_document_normalizer import (
    DoclingDocumentNormalizer,
)


class DoclingDocumentParser:
    name = "docling"

    def __init__(
        self,
        *,
        converter: Any | None = None,
        converter_factory: DoclingConverterFactory | None = None,
        normalizer: DoclingDocumentNormalizer | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._converter = converter
        self._converter_factory = converter_factory or DoclingConverterFactory()
        self._normalizer = normalizer or DoclingDocumentNormalizer()
        self._settings = settings or get_settings()

    def parse(
        self,
        file_path: Path,
        *,
        document_id: str | None = None,
        pipeline: str | None = None,
        profile: str | None = None,
    ) -> ParseOutput:
        settings = resolve_profile_settings(self._settings, profile=profile)
        source_path = file_path.expanduser().resolve()
        if not source_path.is_file():
            raise FileNotFoundError(f"Input file does not exist: {source_path}")

        input_format = detect_input_format(source_path)
        validate_allowed_format(input_format, settings.docling_allowed_formats)
        resolved_pipeline = resolve_pipeline_mode(
            pipeline or settings.docling_pipeline,
            input_format,
        )

        converter = self._converter or self._converter_factory.create(
            settings,
            pipeline=resolved_pipeline,
            input_format=input_format,
        )
        result = converter.convert(source_path)
        return self._parse_conversion_result(
            result,
            source_path=source_path,
            settings=settings,
            document_id=document_id,
            input_format=input_format,
            resolved_pipeline=resolved_pipeline,
        )

    def parse_many(
        self,
        file_paths: Iterable[Path],
        *,
        pipeline: str | None = None,
        profile: str | None = None,
    ) -> list[ParseOutput]:
        settings = resolve_profile_settings(self._settings, profile=profile)
        source_paths = [path.expanduser().resolve() for path in file_paths]
        for source_path in source_paths:
            if not source_path.is_file():
                raise FileNotFoundError(f"Input file does not exist: {source_path}")

        input_formats = [detect_input_format(source_path) for source_path in source_paths]
        for input_format in input_formats:
            validate_allowed_format(input_format, settings.docling_allowed_formats)

        resolved_pipelines = [
            resolve_pipeline_mode(pipeline or settings.docling_pipeline, input_format)
            for input_format in input_formats
        ]
        if len(set(resolved_pipelines)) > 1:
            raise ValueError(
                "Batch conversion requires a single resolved pipeline. "
                f"Got: {', '.join(sorted(set(resolved_pipelines)))}."
            )
        resolved_pipeline = resolved_pipelines[0] if resolved_pipelines else "standard"

        converter = self._converter or self._converter_factory.create(
            settings,
            pipeline=resolved_pipeline,
            input_format=None,
        )
        results = converter.convert_all(source_paths, raises_on_error=False)
        return [
            self._parse_conversion_result(
                result,
                source_path=self._source_path_from_result(result, fallback_path),
                settings=settings,
                document_id=None,
                input_format=input_format,
                resolved_pipeline=resolved_pipeline,
            )
            for fallback_path, input_format, result in zip(
                source_paths,
                input_formats,
                results,
                strict=False,
            )
        ]

    def _parse_conversion_result(
        self,
        result: Any,
        *,
        source_path: Path,
        settings: Settings,
        document_id: str | None,
        input_format: str,
        resolved_pipeline: str,
    ) -> ParseOutput:
        document = result.document
        result_metadata = conversion_result_metadata(result, settings)
        if result_metadata.get("warnings") and not settings.confidence_warn_only:
            raise ValueError(f"Docling confidence validation failed: {result_metadata['warnings']}")
        raw_docling = document.export_to_dict()
        raw_markdown = document.export_to_markdown()
        raw_text = document.export_to_text()
        raw_html = self._try_export_html(document)
        mime_type = mimetypes.guess_type(source_path.name)[0]
        resolved_document_id = document_id or str(uuid4())

        normalized = self._normalizer.normalize(
            raw_docling=raw_docling,
            source_path=source_path,
            document_id=resolved_document_id,
            markdown=raw_markdown,
            text=raw_text,
            mime_type=mime_type,
        )
        normalized.metadata["docling"] = {
            "parser": self.name,
            "profile": settings.profile,
            "input_format": input_format,
            "pipeline": resolved_pipeline,
            "ocr_engine": settings.docling_pdf_ocr_engine,
            "vlm_model": settings.docling_vlm_model if resolved_pipeline == "vlm" else None,
            "vlm_runtime": settings.docling_vlm_runtime if resolved_pipeline == "vlm" else None,
        }
        normalized.metadata["docling_options"] = docling_options_metadata(
            settings,
            input_format=input_format,
            pipeline=resolved_pipeline,
        )
        normalized.metadata["docling_result"] = result_metadata

        return ParseOutput(
            document=normalized,
            raw_docling=raw_docling,
            raw_markdown=raw_markdown,
            raw_text=raw_text,
            raw_html=raw_html,
            docling_document=document,
            conversion_status=result_metadata.get("status"),
            conversion_errors=result_metadata.get("errors") or [],
            conversion_timings=result_metadata.get("timings") or {},
            confidence=result_metadata.get("confidence"),
            confidence_summary=result_metadata.get("confidence_summary") or {},
            warnings=result_metadata.get("warnings") or [],
        )

    @staticmethod
    def _source_path_from_result(result: Any, fallback: Path) -> Path:
        input_document = getattr(result, "input", None)
        file_path = getattr(input_document, "file", None)
        return Path(file_path) if file_path is not None else fallback

    @staticmethod
    def _try_export_html(document: Any) -> str | None:
        export_to_html = getattr(document, "export_to_html", None)
        if export_to_html is None:
            return None

        try:
            return export_to_html()
        except Exception:
            return None
