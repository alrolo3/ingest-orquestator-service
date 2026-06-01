from __future__ import annotations

import mimetypes
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from uuid import uuid4

from ingest_orquestator_server.config.settings import Settings, get_settings
from ingest_orquestator_server.infrastructure.docling.docling_converter_factory import (
    DoclingConverterFactory,
)
from ingest_orquestator_server.infrastructure.docling.docling_engine import (
    DoclingConversionScheduler,
)
from ingest_orquestator_server.infrastructure.docling.docling_format_routes import (
    route_metadata_for,
)
from ingest_orquestator_server.infrastructure.docling.docling_formats import (
    detect_input_format,
    resolve_pipeline_mode,
    validate_allowed_format,
)
from ingest_orquestator_server.infrastructure.docling.docling_options import (
    docling_options_metadata,
)
from ingest_orquestator_server.infrastructure.docling.docling_progress import (
    docling_progress_context,
    estimate_source_page_count,
)
from ingest_orquestator_server.infrastructure.docling.docling_result_metadata import (
    conversion_result_metadata,
)
from ingest_orquestator_server.infrastructure.docling.docling_runtime_capabilities import (
    docling_runtime_metadata,
    resolve_picture_description_runtime,
    resolve_vlm_convert_runtime,
)
from ingest_orquestator_server.models.parse_output import ParseOutput
from ingest_orquestator_server.models.parse_progress import (
    ParseProgressCallback,
    ParseProgressUpdate,
)
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
        conversion_scheduler: DoclingConversionScheduler | None = None,
        normalizer: DoclingDocumentNormalizer | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._converter = converter
        self._converter_factory = converter_factory or DoclingConverterFactory()
        self._conversion_scheduler = conversion_scheduler
        self._normalizer = normalizer or DoclingDocumentNormalizer()
        self._settings = settings or get_settings()

    def parse(
        self,
        file_path: Path,
        *,
        document_id: str | None = None,
        pipeline: str | None = None,
        ocr_languages: list[str] | None = None,
        include_html: bool = False,
        progress_callback: ParseProgressCallback | None = None,
    ) -> ParseOutput:
        settings = self._effective_settings(ocr_languages)
        source_path = file_path.expanduser().resolve()
        if not source_path.is_file():
            raise FileNotFoundError(f"Input file does not exist: {source_path}")

        input_format = detect_input_format(source_path)
        self._report_progress(
            progress_callback,
            ParseProgressUpdate(
                component="docling",
                stage="docling.input.detected",
                message="Docling input format detected.",
                input_format=input_format,
                pipeline=pipeline or settings.docling_pipeline,
                details={"source_file_name": source_path.name},
            ),
        )
        validate_allowed_format(input_format, settings.docling_allowed_formats)
        resolved_pipeline = resolve_pipeline_mode(
            pipeline or settings.docling_pipeline,
            input_format,
        )
        estimated_page_count = estimate_source_page_count(source_path, input_format)
        self._report_progress(
            progress_callback,
            ParseProgressUpdate(
                component="docling",
                stage="docling.pipeline.resolved",
                message="Docling pipeline resolved.",
                input_format=input_format,
                pipeline=resolved_pipeline,
                page_count=estimated_page_count,
                pages_completed=0 if estimated_page_count is not None else None,
                details={
                    "ocr_enabled": settings.docling_pdf_do_ocr,
                    "ocr_engine": settings.docling_pdf_ocr_engine
                    if settings.docling_pdf_do_ocr
                    else None,
                    "ocr_languages": settings.docling_pdf_ocr_languages
                    if settings.docling_pdf_do_ocr
                    else None,
                    "picture_description_enabled": settings.docling_pdf_do_picture_description,
                    "picture_description_model": settings.docling_pdf_picture_description_model
                    if settings.docling_pdf_do_picture_description
                    else None,
                    "vlm_model": settings.docling_vlm_model if resolved_pipeline == "vlm" else None,
                    "remote_llm_url": settings.docling_remote_llm_url
                    if resolved_pipeline == "vlm" and settings.docling_vlm_runtime == "remote_llm"
                    else None,
                    "remote_llm_concurrency": settings.docling_remote_llm_concurrency
                    if resolved_pipeline == "vlm" and settings.docling_vlm_runtime == "remote_llm"
                    else None,
                    "accelerator_device": settings.docling_accelerator_device,
                },
            ),
        )

        engine_metadata: dict[str, Any] | None = None
        with docling_progress_context(
            callback=progress_callback,
            input_format=input_format,
            pipeline=resolved_pipeline,
            page_count=estimated_page_count,
            heartbeat_interval_seconds=settings.progress_log_interval_seconds,
            page_log_interval=settings.progress_page_interval,
        ) as progress:
            if progress is not None:
                progress.report(
                    stage="docling.convert.started",
                    message="Docling conversion started.",
                    pages_completed=0 if estimated_page_count is not None else None,
                )
            result, engine_metadata = self._convert_one(
                source_path,
                settings=settings,
                input_format=input_format,
                pipeline=resolved_pipeline,
            )
            if progress is not None:
                progress.report(
                    stage="docling.convert.completed",
                    message="Docling conversion completed.",
                    page_count=getattr(getattr(result, "input", None), "page_count", None)
                    or estimated_page_count,
                    pages_completed=(
                        getattr(getattr(result, "input", None), "page_count", None)
                        or progress.pages_completed
                    ),
                )
        return self._parse_conversion_result(
            result,
            source_path=source_path,
            settings=settings,
            document_id=document_id,
            input_format=input_format,
            resolved_pipeline=resolved_pipeline,
            engine_metadata=engine_metadata,
            include_html=include_html,
            progress_callback=progress_callback,
        )

    def parse_many(
        self,
        file_paths: Iterable[Path],
        *,
        pipeline: str | None = None,
        ocr_languages: list[str] | None = None,
        include_html: bool = False,
    ) -> list[ParseOutput]:
        settings = self._effective_settings(ocr_languages)
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

        indexed_outputs: list[ParseOutput | None] = [None] * len(source_paths)
        grouped: dict[tuple[str, str], list[tuple[int, Path]]] = {}
        for index, (source_path, input_format, resolved_pipeline) in enumerate(
            zip(source_paths, input_formats, resolved_pipelines, strict=True)
        ):
            grouped.setdefault((input_format, resolved_pipeline), []).append((index, source_path))

        for (input_format, group_pipeline), group_items in grouped.items():
            group_paths = [source_path for _index, source_path in group_items]
            results, engine_metadata = self._convert_many(
                group_paths,
                settings=settings,
                input_format=input_format,
                pipeline=group_pipeline,
            )
            for (index, fallback_path), result in zip(group_items, results, strict=False):
                indexed_outputs[index] = self._parse_conversion_result(
                    result,
                    source_path=self._source_path_from_result(result, fallback_path),
                    settings=settings,
                    document_id=None,
                    input_format=input_format,
                    resolved_pipeline=group_pipeline,
                    engine_metadata=engine_metadata,
                    include_html=include_html,
                )

        return [output for output in indexed_outputs if output is not None]

    def _parse_conversion_result(
        self,
        result: Any,
        *,
        source_path: Path,
        settings: Settings,
        document_id: str | None,
        input_format: str,
        resolved_pipeline: str,
        engine_metadata: dict[str, Any] | None = None,
        include_html: bool = False,
        progress_callback: ParseProgressCallback | None = None,
    ) -> ParseOutput:
        document = result.document
        self._report_progress(
            progress_callback,
            ParseProgressUpdate(
                component="docling",
                stage="docling.normalize.started",
                message="Normalizing Docling output.",
                input_format=input_format,
                pipeline=resolved_pipeline,
            ),
        )
        result_metadata = conversion_result_metadata(result, settings)
        if result_metadata.get("warnings") and not settings.confidence_warn_only:
            raise ValueError(f"Docling confidence validation failed: {result_metadata['warnings']}")
        raw_docling = document.export_to_dict()
        raw_markdown = document.export_to_markdown()
        raw_text = document.export_to_text()
        raw_html = self._try_export_html(document) if include_html else None
        mime_type = mimetypes.guess_type(source_path.name)[0]
        resolved_document_id = document_id or str(uuid4())
        runtime_metadata = docling_runtime_metadata(settings, pipeline=resolved_pipeline)
        vlm_resolution = resolve_vlm_convert_runtime(settings)
        picture_resolution = resolve_picture_description_runtime(settings)

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
            "input_format": input_format,
            "pipeline": resolved_pipeline,
            "route": route_metadata_for(
                input_format=input_format,
                pipeline=resolved_pipeline,
            ),
            "ocr_engine": settings.docling_pdf_ocr_engine,
            "ocr_languages": settings.docling_pdf_ocr_languages,
            "vlm_model": settings.docling_vlm_model if resolved_pipeline == "vlm" else None,
            "vlm_runtime": vlm_resolution.resolved_runtime if resolved_pipeline == "vlm" else None,
            "vlm_runtime_requested": settings.docling_vlm_runtime
            if resolved_pipeline == "vlm"
            else None,
            "picture_description_model": settings.docling_pdf_picture_description_model
            if settings.docling_pdf_do_picture_description
            else None,
            "picture_description_runtime": picture_resolution.resolved_runtime
            if settings.docling_pdf_do_picture_description
            else None,
            "picture_description_runtime_requested": (
                settings.docling_pdf_picture_description_runtime
                if settings.docling_pdf_do_picture_description
                else None
            ),
            "runtime": runtime_metadata,
            "engine": engine_metadata,
        }
        normalized.metadata["docling_options"] = docling_options_metadata(
            settings,
            input_format=input_format,
            pipeline=resolved_pipeline,
        )
        normalized.metadata["docling_result"] = result_metadata
        self._report_progress(
            progress_callback,
            ParseProgressUpdate(
                component="docling",
                stage="docling.normalize.completed",
                message="Docling output normalized.",
                input_format=input_format,
                pipeline=resolved_pipeline,
                page_count=normalized.page_count,
                pages_completed=normalized.page_count,
                details={
                    "element_count": len(normalized.elements),
                    "conversion_status": result_metadata.get("status"),
                },
            ),
        )

        safe_metadata = {
            "source_file_name": normalized.source_file_name,
            "page_count": normalized.page_count,
            "element_count": len(normalized.elements),
            "input_format": input_format,
            "pipeline": resolved_pipeline,
            "route": route_metadata_for(
                input_format=input_format,
                pipeline=resolved_pipeline,
            ),
            "ocr_engine": settings.docling_pdf_ocr_engine,
            "ocr_languages": settings.docling_pdf_ocr_languages,
            "vlm_model": settings.docling_vlm_model if resolved_pipeline == "vlm" else None,
            "vlm_runtime": vlm_resolution.resolved_runtime if resolved_pipeline == "vlm" else None,
            "vlm_runtime_requested": settings.docling_vlm_runtime
            if resolved_pipeline == "vlm"
            else None,
            "picture_description_model": settings.docling_pdf_picture_description_model
            if settings.docling_pdf_do_picture_description
            else None,
            "picture_description_runtime": picture_resolution.resolved_runtime
            if settings.docling_pdf_do_picture_description
            else None,
            "picture_description_runtime_requested": (
                settings.docling_pdf_picture_description_runtime
                if settings.docling_pdf_do_picture_description
                else None
            ),
            "runtime": {
                "active_pipeline_stage": normalized.metadata["docling"]["runtime"].get(
                    "active_pipeline_stage"
                ),
                "stages": normalized.metadata["docling"]["runtime"].get("stages"),
            },
            "engine": engine_metadata,
        }

        return ParseOutput(
            document_id=normalized.document_id,
            source_file_name=normalized.source_file_name,
            title=normalized.title,
            markdown=raw_markdown,
            html=raw_html,
            metadata={key: value for key, value in safe_metadata.items() if value is not None},
            normalized_document=normalized,
            chunking_document=document,
            conversion_status=result_metadata.get("status"),
            conversion_errors=result_metadata.get("errors") or [],
            conversion_timings=result_metadata.get("timings") or {},
            confidence_summary=result_metadata.get("confidence_summary") or {},
            warnings=result_metadata.get("warnings") or [],
        )

    def _convert_one(
        self,
        source_path: Path,
        *,
        settings: Settings,
        input_format: str,
        pipeline: str,
    ) -> tuple[Any, dict[str, Any] | None]:
        if self._converter is not None:
            return self._converter.convert(source_path), None
        if self._conversion_scheduler is not None:
            return self._conversion_scheduler.convert(
                source_path,
                settings=settings,
                input_format=input_format,
                pipeline=pipeline,
            )
        converter = self._converter_factory.create(
            settings,
            pipeline=pipeline,
            input_format=input_format,
        )
        return converter.convert(source_path), None

    def _convert_many(
        self,
        source_paths: list[Path],
        *,
        settings: Settings,
        input_format: str,
        pipeline: str,
    ) -> tuple[list[Any], dict[str, Any] | None]:
        if self._converter is not None:
            return (
                list(self._converter.convert_all(source_paths, raises_on_error=False)),
                None,
            )
        if self._conversion_scheduler is not None:
            return self._conversion_scheduler.convert_all(
                source_paths,
                settings=settings,
                input_format=input_format,
                pipeline=pipeline,
            )
        converter = self._converter_factory.create(
            settings,
            pipeline=pipeline,
            input_format=input_format,
        )
        return list(converter.convert_all(source_paths, raises_on_error=False)), None

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

    def _effective_settings(self, ocr_languages: list[str] | None) -> Settings:
        if ocr_languages is None:
            return self._settings
        return self._settings.model_copy(
            update={"docling_pdf_ocr_languages": list(ocr_languages)}
        )

    @staticmethod
    def _report_progress(
        callback: ParseProgressCallback | None,
        update: ParseProgressUpdate,
    ) -> None:
        if callback is None:
            return
        callback(update)
