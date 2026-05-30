from __future__ import annotations

from pathlib import Path

from ingest_orquestator_server.application.exceptions import (
    UnsupportedDocumentFormatError,
    UnsupportedPipelineError,
)

SUPPORTED_PIPELINES = {"standard", "vlm", "auto"}
VLM_SUPPORTED_FORMATS = {"pdf", "image"}

EXTENSION_TO_FORMAT = {
    ".adoc": "asciidoc",
    ".asciidoc": "asciidoc",
    ".bmp": "image",
    ".csv": "csv",
    ".docx": "docx",
    ".flac": "audio",
    ".htm": "html",
    ".html": "html",
    ".jats": "xml_jats",
    ".jpeg": "image",
    ".jpg": "image",
    ".json": "json_docling",
    ".latex": "latex",
    ".m4a": "audio",
    ".markdown": "md",
    ".md": "md",
    ".mets": "mets_gbs",
    ".mp3": "audio",
    ".nxml": "xml_jats",
    ".pdf": "pdf",
    ".png": "image",
    ".pptx": "pptx",
    ".tex": "latex",
    ".tif": "image",
    ".tiff": "image",
    ".txt": "md",
    ".uspto": "xml_uspto",
    ".vtt": "vtt",
    ".wav": "audio",
    ".webp": "image",
    ".xbrl": "xml_xbrl",
    ".xlsx": "xlsx",
}


def detect_input_format(source_path: Path) -> str:
    extension = source_path.suffix.lower()
    input_format = EXTENSION_TO_FORMAT.get(extension)
    if input_format is None:
        raise UnsupportedDocumentFormatError(
            f"Unsupported document extension '{extension or '<none>'}'. "
            "Configure a supported Docling format before ingesting this file."
        )
    return input_format


def validate_allowed_format(input_format: str, allowed_formats: list[str]) -> None:
    allowed = set(allowed_formats)
    if input_format not in allowed:
        raise UnsupportedDocumentFormatError(
            f"Docling input format '{input_format}' is disabled. "
            f"Allowed formats: {', '.join(sorted(allowed))}."
        )


def resolve_pipeline_mode(requested_pipeline: str, input_format: str) -> str:
    pipeline = requested_pipeline.strip().lower()
    if pipeline not in SUPPORTED_PIPELINES:
        raise UnsupportedPipelineError("Pipeline must be one of standard, vlm, or auto.")
    if pipeline == "auto":
        return "standard"
    if pipeline == "vlm" and input_format not in VLM_SUPPORTED_FORMATS:
        raise UnsupportedPipelineError(
            "Docling VLM pipeline is supported only for PDF and image inputs in v1.2. "
            f"Input format '{input_format}' must use pipeline=standard."
        )
    return pipeline
