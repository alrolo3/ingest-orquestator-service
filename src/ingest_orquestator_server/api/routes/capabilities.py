from typing import Annotated

from fastapi import APIRouter, Depends

from ingest_orquestator_server.api.dependencies import get_docling_conversion_scheduler
from ingest_orquestator_server.config.settings import Settings, get_settings
from ingest_orquestator_server.infrastructure.docling.docling_engine import (
    DoclingConversionScheduler,
)

router = APIRouter(prefix="/v1/ingest")


@router.get("/capabilities")
def ingestion_capabilities(
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    """Return UI-safe ingestion options without loading parser models."""

    return {
        "service": settings.service_name,
        "max_upload_size_mb": settings.max_upload_size_mb,
        "allowed_upload_extensions": settings.allowed_upload_extensions,
        "parsers": [
            {
                "value": "docling",
                "label": "Docling",
                "default": True,
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
        "chunking": {
            "enabled": settings.chunking_enabled,
            "default_strategy": settings.chunking_strategy,
            "strategies": [
                {"value": "hybrid", "label": "Hybrid"},
                {"value": "line_based", "label": "Line Based"},
                {"value": "legacy_char", "label": "Legacy Char"},
            ],
        },
        "runtime": {
            "dispatch_sink_mode": settings.dispatch_sink_mode,
            "parser_worker_count": settings.parser_worker_count,
            "dispatch_max_bulk_size": settings.dispatch_max_bulk_size,
            "embedding_output_enabled": settings.embedding_output_enabled,
            "elastic_index": settings.embedding_elastic_index,
            "elastic_mapping_version": settings.embedding_elastic_mapping_version,
            "elastic_configured": settings.embedding_elastic_url is not None,
            "docling_accelerator_device": settings.docling_accelerator_device,
            "docling_engine_cache_enabled": settings.docling_engine_cache_enabled,
            "docling_engine_warmup_enabled": settings.docling_engine_warmup_enabled,
            "docling_engine_warmup_formats": settings.docling_engine_warmup_formats,
            "docling_gpu_engine_concurrency": settings.docling_gpu_engine_concurrency,
            "docling_gpu_batch_max_documents": settings.docling_gpu_batch_max_documents,
            "docling_gpu_batch_wait_ms": settings.docling_gpu_batch_wait_ms,
            "docling_perf_page_batch_size": settings.docling_perf_page_batch_size,
            "docling_vlm_runtime": settings.docling_vlm_runtime,
            "docling_vlm_model": settings.docling_vlm_model,
            "picture_description_enabled": settings.docling_pdf_do_picture_description,
            "picture_description_model": settings.docling_pdf_picture_description_model,
            "ocr_enabled": settings.docling_pdf_do_ocr,
            "ocr_engine": settings.docling_pdf_ocr_engine,
        },
        "output_types": [
            "manifest",
            "normalized",
            "markdown",
            "text",
            "raw",
            "html",
            "chunks",
            "embedding",
            "confidence",
        ],
        "job_statuses": [
            "parser_queued",
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
