from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any
from uuid import uuid4

from ingest_orquestator_server.config import Settings, get_settings
from ingest_orquestator_server.models import ParseOutput
from ingest_orquestator_server.normalization import normalize_docling_document


class DoclingParser:
    name = "docling"

    def __init__(self, converter: Any | None = None, settings: Settings | None = None) -> None:
        self._converter = converter
        self._settings = settings or get_settings()

    def parse(self, file_path: Path, *, document_id: str | None = None) -> ParseOutput:
        source_path = file_path.expanduser().resolve()
        if not source_path.is_file():
            raise FileNotFoundError(f"Input file does not exist: {source_path}")

        converter = self._converter or self._create_converter(self._settings)
        result = converter.convert(source_path)
        document = result.document
        raw_docling = document.export_to_dict()
        raw_markdown = document.export_to_markdown()
        raw_text = document.export_to_text()
        raw_html = _try_export_html(document)
        mime_type = mimetypes.guess_type(source_path.name)[0]
        resolved_document_id = document_id or str(uuid4())

        normalized = normalize_docling_document(
            raw_docling=raw_docling,
            source_path=source_path,
            document_id=resolved_document_id,
            markdown=raw_markdown,
            text=raw_text,
            mime_type=mime_type,
        )
        normalized.metadata["docling_options"] = _docling_options_metadata(self._settings)

        return ParseOutput(
            document=normalized,
            raw_docling=raw_docling,
            raw_markdown=raw_markdown,
            raw_text=raw_text,
            raw_html=raw_html,
        )

    @classmethod
    def _create_converter(cls, settings: Settings) -> Any:
        try:
            from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption
        except ImportError as exc:
            raise RuntimeError(
                "Docling is not installed. Install project dependencies with "
                "`uv sync --extra dev --python 3.12` or `pip install .`."
            ) from exc

        accelerator_options = AcceleratorOptions(
            num_threads=settings.docling_num_threads,
            device=_docling_accelerator_device(
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

        return DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_pipeline_options),
            }
        )


def _docling_accelerator_device(device: str, accelerator_device: Any) -> Any:
    enum_devices = {
        accelerator_device.AUTO.value: accelerator_device.AUTO,
        accelerator_device.CPU.value: accelerator_device.CPU,
        accelerator_device.CUDA.value: accelerator_device.CUDA,
        accelerator_device.MPS.value: accelerator_device.MPS,
        accelerator_device.XPU.value: accelerator_device.XPU,
    }
    return enum_devices.get(device, device)


def _docling_options_metadata(settings: Settings) -> dict[str, Any]:
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


def _try_export_html(document: Any) -> str | None:
    export_to_html = getattr(document, "export_to_html", None)
    if export_to_html is None:
        return None

    try:
        return export_to_html()
    except Exception:
        return None
