from typing import Annotated

from fastapi import APIRouter, Depends

from ingest_orquestator_server.api.dependencies import (
    SettingsDependency,
    get_docling_conversion_scheduler,
)
from ingest_orquestator_server.application.services.ingestion_request_options import (
    DEFAULT_OCR_LANGUAGE_OPTIONS,
    DISPATCH_SINK_MODES,
)
from ingest_orquestator_server.infrastructure.docling.docling_engine import (
    DoclingConversionScheduler,
)
from ingest_orquestator_server.infrastructure.parser.parser_chunking_factory import (
    build_parser_chunking_service,
)

router = APIRouter(prefix="/v1/ingest")


@router.get("/capabilities")
def ingestion_capabilities(
    settings: SettingsDependency,
) -> dict[str, object]:
    """Return UI-safe ingestion options without loading parser models."""

    chunking_service = build_parser_chunking_service(settings)
    docling_chunking = chunking_service.capabilities_for("docling")
    docling_chunking_payload = docling_chunking.model_dump(mode="json")

    return {
        "service": settings.service_name,
        "max_upload_size_mb": settings.max_upload_size_mb,
        "allowed_upload_extensions": settings.allowed_upload_extensions,
        "parsers": [
            {
                "value": "docling",
                "label": "Docling",
                "default": True,
                "chunking": docling_chunking_payload,
            }
        ],
        "pipelines": [
            {
                "value": "standard",
                "label": "Standard",
                "default": settings.docling_pipeline == "standard",
                "supported_input_formats": settings.docling_allowed_formats,
            },
            {
                "value": "vlm",
                "label": "VLM",
                "default": settings.docling_pipeline == "vlm",
                "supported_input_formats": ["pdf", "image"],
            },
            {
                "value": "auto",
                "label": "Auto",
                "default": settings.docling_pipeline == "auto",
                "supported_input_formats": settings.docling_allowed_formats,
            },
        ],
        "default_parser": "docling",
        "default_pipeline": settings.docling_pipeline,
        "default_dispatch_sink_mode": settings.dispatch_sink_mode,
        "dispatchers": [
            {
                "value": value,
                "label": value.replace("_", " ").title(),
                "default": value == settings.dispatch_sink_mode,
            }
            for value in DISPATCH_SINK_MODES
        ],
        "ocr": {
            "enabled": settings.docling_pdf_do_ocr,
            "engine": settings.docling_pdf_ocr_engine,
            "default_languages": settings.docling_pdf_ocr_languages,
            "languages": [
                {
                    "value": value,
                    "label": label,
                    "default": value in settings.docling_pdf_ocr_languages,
                }
                for value, label in DEFAULT_OCR_LANGUAGE_OPTIONS
            ],
        },
        "chunking": {
            "enabled": settings.chunking_enabled,
            "default_strategy": docling_chunking_payload["default_strategy"],
            "strategies": docling_chunking_payload["strategies"],
            "by_parser": {
                "docling": docling_chunking_payload,
            },
        },
        "runtime": {
            "dispatch_sink_mode": settings.dispatch_sink_mode,
            "parser_process_count": settings.parser_process_count,
            "parser_threads_per_process": settings.parser_threads_per_process,
            "parser_worker_count": settings.parser_worker_count,
            "docling_parse_concurrency": settings.effective_docling_parse_concurrency,
            "dispatch_process_count": settings.dispatch_process_count,
            "dispatch_threads_per_process": settings.dispatch_threads_per_process,
            "dispatch_max_bulk_size": settings.dispatch_max_bulk_size,
            "embedding_output_enabled": settings.embedding_output_enabled,
            "elastic_index": settings.embedding_elastic_index,
            "elastic_mapping_version": settings.embedding_elastic_mapping_version,
            "elastic_configured": settings.embedding_elastic_url is not None,
            "docling_accelerator_device": settings.docling_accelerator_device,
            "docling_engine_cache_enabled": settings.docling_engine_cache_enabled,
            "docling_engine_warmup_enabled": settings.docling_engine_warmup_enabled,
            "docling_engine_warmup_formats": settings.docling_engine_warmup_formats,
            "docling_perf_page_batch_size": settings.docling_perf_page_batch_size,
            "docling_vlm_model": settings.docling_vlm_model,
            "picture_description_enabled": settings.docling_pdf_do_picture_description,
            "picture_description_model": settings.docling_pdf_picture_description_model,
            "ocr_enabled": settings.docling_pdf_do_ocr,
            "ocr_engine": settings.docling_pdf_ocr_engine,
        },
        "output_types": [
            "metadata",
            "markdown",
            "rag",
            "html",
        ],
        "job_statuses": [
            "parser_queued",
            "retrying",
            "parsing",
            "parsed",
            "dispatch_queued",
            "dispatching",
            "stored_local",
            "indexed_elastic",
            "retryable_failure",
            "completed",
            "failed",
        ],
    }


@router.get("/docling/engines")
def docling_engine_diagnostics(
    scheduler: Annotated[
        DoclingConversionScheduler,
        Depends(get_docling_conversion_scheduler),
    ],
) -> dict[str, object]:
    """Return current Docling engine cache state without loading new models."""

    return scheduler.snapshot()
