from __future__ import annotations

from typing import Any

from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.docling.docling_model_options import (
    build_code_formula_options,
    build_layout_options,
    build_ocr_options,
    build_picture_classification_options,
    build_picture_description_options,
    build_table_structure_options,
    build_vlm_convert_options,
)
from ingest_orquestator_server.infrastructure.docling.docling_runtime_capabilities import (
    RUNTIME_REMOTE_LLM,
    docling_runtime_metadata,
    resolve_picture_description_runtime,
    resolve_vlm_convert_runtime,
)


def build_pdf_pipeline_options(settings: Settings) -> Any:
    try:
        from docling.datamodel.pipeline_options import PdfPipelineOptions
    except ImportError as exc:
        raise RuntimeError(
            "Docling is not installed. Install project dependencies with "
            "`python -m pip install -e .` inside the project virtual environment."
        ) from exc

    _configure_docling_perf_page_batch_size(settings)
    pdf_pipeline_options = PdfPipelineOptions()
    pdf_pipeline_options.accelerator_options = build_accelerator_options(settings)
    picture_description_uses_remote_llm = (
        settings.docling_pdf_do_picture_description
        and resolve_picture_description_runtime(settings).resolved_runtime == RUNTIME_REMOTE_LLM
    )
    if picture_description_uses_remote_llm:
        _configure_remote_llm_docling_batch_size(settings)
    pdf_pipeline_options.enable_remote_services = picture_description_uses_remote_llm
    pdf_pipeline_options.allow_external_plugins = settings.docling_allow_external_plugins
    pdf_pipeline_options.do_ocr = settings.docling_pdf_do_ocr
    pdf_pipeline_options.ocr_options = build_ocr_options(settings)
    pdf_pipeline_options.do_table_structure = settings.docling_pdf_do_table_structure
    pdf_pipeline_options.table_structure_options = build_table_structure_options(settings)
    pdf_pipeline_options.layout_options = build_layout_options(settings)
    pdf_pipeline_options.do_picture_classification = settings.docling_pdf_do_picture_classification
    pdf_pipeline_options.picture_classification_options = build_picture_classification_options(
        settings
    )
    pdf_pipeline_options.do_picture_description = settings.docling_pdf_do_picture_description
    pdf_pipeline_options.picture_description_options = build_picture_description_options(settings)
    pdf_pipeline_options.do_code_enrichment = settings.docling_pdf_do_code_enrichment
    pdf_pipeline_options.do_formula_enrichment = settings.docling_pdf_do_formula_enrichment
    pdf_pipeline_options.code_formula_options = build_code_formula_options(settings)
    pdf_pipeline_options.ocr_batch_size = settings.docling_pdf_ocr_batch_size
    pdf_pipeline_options.layout_batch_size = settings.docling_pdf_layout_batch_size
    pdf_pipeline_options.table_batch_size = settings.docling_pdf_table_batch_size
    pdf_pipeline_options.queue_max_size = settings.docling_pdf_queue_max_size
    return pdf_pipeline_options


def build_vlm_pipeline_options(settings: Settings) -> Any:
    try:
        from docling.datamodel.pipeline_options import VlmPipelineOptions
    except ImportError as exc:
        raise RuntimeError(
            "Docling is not installed. Install project dependencies with "
            "`python -m pip install -e .` inside the project virtual environment."
        ) from exc

    _configure_docling_perf_page_batch_size(settings)
    resolution = resolve_vlm_convert_runtime(settings)
    if resolution.resolved_runtime == RUNTIME_REMOTE_LLM:
        _configure_remote_llm_docling_batch_size(settings)

    return VlmPipelineOptions(
        accelerator_options=build_accelerator_options(settings),
        enable_remote_services=resolution.resolved_runtime == RUNTIME_REMOTE_LLM,
        allow_external_plugins=settings.docling_allow_external_plugins,
        images_scale=settings.docling_vlm_scale,
        generate_page_images=True,
        vlm_options=build_vlm_convert_options(settings),
    )


def _configure_remote_llm_docling_batch_size(settings: Settings) -> None:
    from docling.datamodel.settings import settings as docling_settings

    page_batch_size = (
        settings.docling_remote_llm_page_batch_size or settings.docling_remote_llm_concurrency
    )
    if docling_settings.perf.page_batch_size < page_batch_size:
        docling_settings.perf.page_batch_size = page_batch_size


def _configure_docling_perf_page_batch_size(settings: Settings) -> None:
    if settings.docling_perf_page_batch_size is None:
        return
    from docling.datamodel.settings import settings as docling_settings

    docling_settings.perf.page_batch_size = settings.docling_perf_page_batch_size


def build_convert_pipeline_options(settings: Settings) -> Any:
    try:
        from docling.datamodel.pipeline_options import ConvertPipelineOptions
    except ImportError as exc:
        raise RuntimeError(
            "Docling is not installed. Install project dependencies with "
            "`python -m pip install -e .` inside the project virtual environment."
        ) from exc

    _configure_docling_perf_page_batch_size(settings)
    return ConvertPipelineOptions(
        accelerator_options=build_accelerator_options(settings),
        allow_external_plugins=settings.docling_allow_external_plugins,
    )


def build_accelerator_options(settings: Settings) -> Any:
    from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions

    return AcceleratorOptions(
        num_threads=settings.docling_num_threads,
        device=docling_accelerator_device(
            settings.docling_accelerator_device,
            AcceleratorDevice,
        ),
        cuda_use_flash_attention2=settings.docling_cuda_use_flash_attention2,
    )


def docling_accelerator_device(device: str, accelerator_device: Any) -> Any:
    enum_devices = {
        accelerator_device.AUTO.value: accelerator_device.AUTO,
        accelerator_device.CPU.value: accelerator_device.CPU,
        accelerator_device.CUDA.value: accelerator_device.CUDA,
        accelerator_device.MPS.value: accelerator_device.MPS,
        accelerator_device.XPU.value: accelerator_device.XPU,
    }
    return enum_devices.get(device, device)


def docling_options_metadata(
    settings: Settings,
    *,
    input_format: str | None = None,
    pipeline: str | None = None,
) -> dict[str, Any]:
    resolved_pipeline = pipeline or settings.docling_pipeline
    return {
        "common": _common_options(settings, input_format=input_format, pipeline=resolved_pipeline),
        "runtime": docling_runtime_metadata(settings, pipeline=resolved_pipeline),
        "active_options": _active_options(
            settings,
            input_format=input_format,
            pipeline=resolved_pipeline,
        ),
        "configured_options": {
            "pdf": _pdf_options(settings),
            "vlm": _vlm_options(settings),
            "xbrl": _xbrl_options(settings),
            "chunking": {
                "enabled": settings.chunking_enabled,
                "strategy": settings.chunking_strategy,
                "max_tokens": settings.chunk_max_tokens,
                "tokenizer_model": settings.chunk_tokenizer_model,
                "merge_peers": settings.chunk_merge_peers,
                "repeat_table_header": settings.chunk_repeat_table_header,
                "omit_header_on_overflow": settings.chunk_omit_header_on_overflow,
                "omit_prefix_on_overflow": settings.chunk_omit_prefix_on_overflow,
                "legacy_chunk_size_chars": settings.chunk_size_chars,
                "legacy_chunk_overlap_chars": settings.chunk_overlap_chars,
            },
            "confidence": {
                "output_enabled": settings.confidence_output_enabled,
                "min_document_score": settings.confidence_min_document_score,
                "warn_only": settings.confidence_warn_only,
            },
        },
    }


def _common_options(
    settings: Settings,
    *,
    input_format: str | None,
    pipeline: str,
) -> dict[str, Any]:
    return {
        "parser": "docling",
        "input_format": input_format,
        "pipeline": pipeline,
        "allowed_formats": settings.docling_allowed_formats,
        "accelerator_device": settings.docling_accelerator_device,
        "num_threads": settings.docling_num_threads,
        "cuda_use_flash_attention2": settings.docling_cuda_use_flash_attention2,
        "allow_external_plugins": settings.docling_allow_external_plugins,
        "remote_llm_provider": settings.docling_remote_llm_provider,
        "remote_llm_url": settings.docling_remote_llm_url,
        "remote_llm_api_key_configured": settings.docling_remote_llm_api_key is not None,
        "engine_cache_enabled": settings.docling_engine_cache_enabled,
        "engine_warmup_enabled": settings.docling_engine_warmup_enabled,
        "engine_warmup_formats": settings.docling_engine_warmup_formats,
        "gpu_engine_concurrency": settings.docling_gpu_engine_concurrency,
        "gpu_batch_max_documents": settings.docling_gpu_batch_max_documents,
        "gpu_batch_wait_ms": settings.docling_gpu_batch_wait_ms,
        "engine_idle_ttl_seconds": settings.docling_engine_idle_ttl_seconds,
        "perf_page_batch_size": settings.docling_perf_page_batch_size,
    }


def _active_options(
    settings: Settings,
    *,
    input_format: str | None,
    pipeline: str,
) -> dict[str, Any]:
    if pipeline == "vlm" and input_format in {"pdf", "image"}:
        return {
            "format": input_format,
            "pipeline": "vlm",
            "format_option": "PdfFormatOption" if input_format == "pdf" else "ImageFormatOption",
            "pipeline_options": _vlm_options(settings),
        }
    if input_format == "pdf":
        return {
            "format": "pdf",
            "pipeline": "standard",
            "format_option": "PdfFormatOption",
            "pipeline_options": _pdf_options(settings),
        }
    if input_format == "image":
        return {
            "format": "image",
            "pipeline": "standard",
            "format_option": "ImageFormatOption",
            "pipeline_options": _pdf_options(settings),
        }
    if input_format == "xml_xbrl":
        return {
            "format": "xml_xbrl",
            "pipeline": "standard",
            "format_option": "XBRLFormatOption",
            "backend_options": _xbrl_options(settings),
        }
    return {
        "format": input_format,
        "pipeline": pipeline,
        "uses_docling_defaults": True,
    }


def _pdf_options(settings: Settings) -> dict[str, Any]:
    return {
        "do_ocr": settings.docling_pdf_do_ocr,
        "ocr_engine": settings.docling_pdf_ocr_engine,
        "ocr_languages": settings.docling_pdf_ocr_languages,
        "ocr_use_gpu": settings.docling_pdf_ocr_use_gpu,
        "do_table_structure": settings.docling_pdf_do_table_structure,
        "layout_model": settings.docling_pdf_layout_model,
        "table_structure_backend": settings.docling_pdf_table_structure_backend,
        "table_structure_mode": settings.docling_pdf_table_structure_mode,
        "table_do_cell_matching": settings.docling_pdf_table_do_cell_matching,
        "table_structure_vlm_model": settings.docling_pdf_table_structure_vlm_model,
        "do_picture_classification": settings.docling_pdf_do_picture_classification,
        "picture_classifier_preset": settings.docling_pdf_picture_classifier_preset,
        "do_picture_description": settings.docling_pdf_do_picture_description,
        "picture_description_model": settings.docling_pdf_picture_description_model,
        "picture_description_runtime": settings.docling_pdf_picture_description_runtime,
        "picture_description_prompt": settings.docling_pdf_picture_description_prompt,
        "picture_description_max_new_tokens": (
            settings.docling_pdf_picture_description_max_new_tokens
        ),
        "do_code_enrichment": settings.docling_pdf_do_code_enrichment,
        "do_formula_enrichment": settings.docling_pdf_do_formula_enrichment,
        "code_formula_preset": settings.docling_pdf_code_formula_preset,
        "ocr_batch_size": settings.docling_pdf_ocr_batch_size,
        "layout_batch_size": settings.docling_pdf_layout_batch_size,
        "table_batch_size": settings.docling_pdf_table_batch_size,
        "queue_max_size": settings.docling_pdf_queue_max_size,
        "perf_page_batch_size": settings.docling_perf_page_batch_size,
    }


def _vlm_options(settings: Settings) -> dict[str, Any]:
    return {
        "model": settings.docling_vlm_model,
        "runtime": settings.docling_vlm_runtime,
        "response_format": settings.docling_vlm_response_format,
        "scale": settings.docling_vlm_scale,
        "torch_dtype": settings.docling_vlm_torch_dtype,
        "load_in_8bit": settings.docling_vlm_load_in_8bit,
        "max_new_tokens": settings.docling_vlm_max_new_tokens,
        "trust_remote_code": settings.effective_docling_vlm_trust_remote_code,
        "remote_llm_url": settings.docling_remote_llm_url,
        "remote_llm_model": settings.docling_remote_llm_model,
        "remote_llm_api_key_configured": settings.docling_remote_llm_api_key is not None,
        "remote_llm_api_key_header": settings.docling_remote_llm_api_key_header,
        "remote_llm_timeout_seconds": settings.docling_remote_llm_timeout_seconds,
        "remote_llm_concurrency": settings.docling_remote_llm_concurrency,
        "remote_llm_page_batch_size": settings.docling_remote_llm_page_batch_size,
        "remote_llm_max_tokens": settings.docling_remote_llm_max_tokens,
        "remote_llm_temperature": settings.docling_remote_llm_temperature,
        "remote_llm_provider": settings.docling_remote_llm_provider,
    }


def _xbrl_options(settings: Settings) -> dict[str, Any]:
    return {
        "enable_local_fetch": settings.docling_xbrl_enable_local_fetch,
        "enable_remote_fetch": settings.docling_xbrl_enable_remote_fetch,
        "taxonomy_path": str(settings.docling_xbrl_taxonomy_path)
        if settings.docling_xbrl_taxonomy_path is not None
        else None,
    }
