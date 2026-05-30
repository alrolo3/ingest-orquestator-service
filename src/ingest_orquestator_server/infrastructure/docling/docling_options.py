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
)


def build_pdf_pipeline_options(settings: Settings) -> Any:
    try:
        from docling.datamodel.pipeline_options import PdfPipelineOptions
    except ImportError as exc:
        raise RuntimeError(
            "Docling is not installed. Install project dependencies with "
            "`python -m pip install -e .` inside the project virtual environment."
        ) from exc

    pdf_pipeline_options = PdfPipelineOptions()
    pdf_pipeline_options.accelerator_options = build_accelerator_options(settings)
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
        from docling.datamodel.pipeline_options_vlm_model import (
            InferenceFramework,
            InlineVlmOptions,
            ResponseFormat,
            TransformersModelType,
        )
    except ImportError as exc:
        raise RuntimeError(
            "Docling is not installed. Install project dependencies with "
            "`python -m pip install -e .` inside the project virtual environment."
        ) from exc

    return VlmPipelineOptions(
        accelerator_options=build_accelerator_options(settings),
        allow_external_plugins=settings.docling_allow_external_plugins,
        images_scale=settings.docling_vlm_scale,
        generate_page_images=True,
        vlm_options=InlineVlmOptions(
            prompt=settings.docling_vlm_prompt,
            repo_id=settings.docling_vlm_model,
            inference_framework=InferenceFramework(settings.docling_vlm_runtime),
            transformers_model_type=TransformersModelType.AUTOMODEL_IMAGETEXTTOTEXT,
            response_format=ResponseFormat(settings.docling_vlm_response_format),
            torch_dtype=settings.docling_vlm_torch_dtype,
            load_in_8bit=settings.docling_vlm_load_in_8bit,
        ),
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
    return {
        "parser": "docling",
        "input_format": input_format,
        "pipeline": pipeline or settings.docling_pipeline,
        "allowed_formats": settings.docling_allowed_formats,
        "accelerator_device": settings.docling_accelerator_device,
        "num_threads": settings.docling_num_threads,
        "cuda_use_flash_attention2": settings.docling_cuda_use_flash_attention2,
        "allow_external_plugins": settings.docling_allow_external_plugins,
        "pdf_do_ocr": settings.docling_pdf_do_ocr,
        "pdf_ocr_engine": settings.docling_pdf_ocr_engine,
        "pdf_ocr_languages": settings.docling_pdf_ocr_languages,
        "pdf_ocr_use_gpu": settings.docling_pdf_ocr_use_gpu,
        "pdf_do_table_structure": settings.docling_pdf_do_table_structure,
        "pdf_layout_model": settings.docling_pdf_layout_model,
        "pdf_table_structure_backend": settings.docling_pdf_table_structure_backend,
        "pdf_table_structure_mode": settings.docling_pdf_table_structure_mode,
        "pdf_table_do_cell_matching": settings.docling_pdf_table_do_cell_matching,
        "pdf_table_structure_vlm_model": settings.docling_pdf_table_structure_vlm_model,
        "pdf_do_picture_classification": settings.docling_pdf_do_picture_classification,
        "pdf_picture_classifier_preset": settings.docling_pdf_picture_classifier_preset,
        "pdf_do_picture_description": settings.docling_pdf_do_picture_description,
        "pdf_picture_description_model": settings.docling_pdf_picture_description_model,
        "pdf_picture_description_prompt": settings.docling_pdf_picture_description_prompt,
        "pdf_do_code_enrichment": settings.docling_pdf_do_code_enrichment,
        "pdf_do_formula_enrichment": settings.docling_pdf_do_formula_enrichment,
        "pdf_code_formula_preset": settings.docling_pdf_code_formula_preset,
        "pdf_ocr_batch_size": settings.docling_pdf_ocr_batch_size,
        "pdf_layout_batch_size": settings.docling_pdf_layout_batch_size,
        "pdf_table_batch_size": settings.docling_pdf_table_batch_size,
        "pdf_queue_max_size": settings.docling_pdf_queue_max_size,
        "vlm_model": settings.docling_vlm_model,
        "vlm_runtime": settings.docling_vlm_runtime,
        "vlm_response_format": settings.docling_vlm_response_format,
        "vlm_scale": settings.docling_vlm_scale,
    }
