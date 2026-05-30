from __future__ import annotations

from typing import Any

from ingest_orquestator_server.config.settings import Settings


def build_pdf_pipeline_options(settings: Settings) -> Any:
    try:
        from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
        from docling.datamodel.pipeline_options import PdfPipelineOptions
    except ImportError as exc:
        raise RuntimeError(
            "Docling is not installed. Install project dependencies with "
            "`uv sync --extra dev --python 3.12` or `pip install .`."
        ) from exc

    accelerator_options = AcceleratorOptions(
        num_threads=settings.docling_num_threads,
        device=docling_accelerator_device(
            settings.docling_accelerator_device,
            AcceleratorDevice,
        ),
        cuda_use_flash_attention2=settings.docling_cuda_use_flash_attention2,
    )
    pdf_pipeline_options = PdfPipelineOptions()
    pdf_pipeline_options.accelerator_options = accelerator_options
    pdf_pipeline_options.do_ocr = settings.docling_pdf_do_ocr
    pdf_pipeline_options.do_table_structure = settings.docling_pdf_do_table_structure
    pdf_pipeline_options.ocr_batch_size = settings.docling_pdf_ocr_batch_size
    pdf_pipeline_options.layout_batch_size = settings.docling_pdf_layout_batch_size
    pdf_pipeline_options.table_batch_size = settings.docling_pdf_table_batch_size
    pdf_pipeline_options.queue_max_size = settings.docling_pdf_queue_max_size
    return pdf_pipeline_options


def docling_accelerator_device(device: str, accelerator_device: Any) -> Any:
    enum_devices = {
        accelerator_device.AUTO.value: accelerator_device.AUTO,
        accelerator_device.CPU.value: accelerator_device.CPU,
        accelerator_device.CUDA.value: accelerator_device.CUDA,
        accelerator_device.MPS.value: accelerator_device.MPS,
        accelerator_device.XPU.value: accelerator_device.XPU,
    }
    return enum_devices.get(device, device)


def docling_options_metadata(settings: Settings) -> dict[str, Any]:
    return {
        "accelerator_device": settings.docling_accelerator_device,
        "num_threads": settings.docling_num_threads,
        "cuda_use_flash_attention2": settings.docling_cuda_use_flash_attention2,
        "pdf_do_ocr": settings.docling_pdf_do_ocr,
        "pdf_do_table_structure": settings.docling_pdf_do_table_structure,
        "pdf_ocr_batch_size": settings.docling_pdf_ocr_batch_size,
        "pdf_layout_batch_size": settings.docling_pdf_layout_batch_size,
        "pdf_table_batch_size": settings.docling_pdf_table_batch_size,
        "pdf_queue_max_size": settings.docling_pdf_queue_max_size,
    }
