from __future__ import annotations

import re
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.docling.docling_runtime_capabilities import (
    RUNTIME_REMOTE_LLM,
)
from ingest_orquestator_server.infrastructure.docling.ocr_engine_registry import (
    OcrEngineRegistry,
)


def build_layout_options(settings: Settings) -> Any:
    from docling.datamodel.layout_model_specs import (
        DOCLING_LAYOUT_EGRET_LARGE,
        DOCLING_LAYOUT_EGRET_MEDIUM,
        DOCLING_LAYOUT_EGRET_XLARGE,
        DOCLING_LAYOUT_HERON,
        DOCLING_LAYOUT_HERON_101,
        DOCLING_LAYOUT_V2,
    )
    from docling.datamodel.pipeline_options import LayoutOptions

    model_specs = {
        "docling-layout-heron": DOCLING_LAYOUT_HERON,
        "docling_layout_heron": DOCLING_LAYOUT_HERON,
        "docling-layout-heron-101": DOCLING_LAYOUT_HERON_101,
        "docling_layout_heron_101": DOCLING_LAYOUT_HERON_101,
        "docling-layout-egret-medium": DOCLING_LAYOUT_EGRET_MEDIUM,
        "docling_layout_egret_medium": DOCLING_LAYOUT_EGRET_MEDIUM,
        "docling-layout-egret-large": DOCLING_LAYOUT_EGRET_LARGE,
        "docling_layout_egret_large": DOCLING_LAYOUT_EGRET_LARGE,
        "docling-layout-egret-xlarge": DOCLING_LAYOUT_EGRET_XLARGE,
        "docling_layout_egret_xlarge": DOCLING_LAYOUT_EGRET_XLARGE,
        "docling-layout-v2": DOCLING_LAYOUT_V2,
        "docling_layout_v2": DOCLING_LAYOUT_V2,
    }
    model_spec = model_specs.get(settings.docling_pdf_layout_model)
    if model_spec is None:
        raise ValueError(
            "Unsupported Docling layout model "
            f"{settings.docling_pdf_layout_model!r}. Supported values: "
            f"{', '.join(sorted(model_specs))}."
        )
    return LayoutOptions(model_spec=model_spec)


def build_ocr_options(settings: Settings) -> Any:
    registry = OcrEngineRegistry(allow_external_plugins=settings.docling_allow_external_plugins)
    try:
        ocr_options = registry.create_options(kind=settings.docling_pdf_ocr_engine)
    except Exception as exc:
        raise RuntimeError(
            "Docling OCR engine "
            f"{settings.docling_pdf_ocr_engine!r} is not available. "
            "For the default SuryaOCR engine, install `docling-surya==0.1.0`, "
            "use Python 3.12+ on Linux x86_64, keep "
            "`INGEST_DOCLING_ALLOW_EXTERNAL_PLUGINS=true`, and pin "
            "`transformers>=4.57,<5`. "
            f"Available engines: {', '.join(registry.available_engines()) or '<none>'}."
        ) from exc

    _validate_surya_transformers_compatibility(settings)

    if settings.docling_pdf_ocr_languages:
        ocr_options.lang = settings.docling_pdf_ocr_languages
    if settings.docling_pdf_ocr_use_gpu is not None and hasattr(ocr_options, "use_gpu"):
        ocr_options.use_gpu = settings.docling_pdf_ocr_use_gpu
    return ocr_options


def build_table_structure_options(settings: Settings) -> Any:
    from docling.datamodel.pipeline_options import (
        TableFormerMode,
        TableStructureOptions,
    )

    return TableStructureOptions(
        do_cell_matching=settings.docling_pdf_table_do_cell_matching,
        mode=TableFormerMode(settings.docling_pdf_table_structure_mode),
    )


def build_picture_classification_options(settings: Settings) -> Any:
    from docling.datamodel.picture_classification_options import (
        DocumentPictureClassifierOptions,
    )

    return DocumentPictureClassifierOptions.from_preset(
        settings.docling_pdf_picture_classifier_preset
    )


def build_picture_description_options(settings: Settings) -> Any:
    from docling.datamodel.pipeline_options import PictureDescriptionApiOptions

    return PictureDescriptionApiOptions(
        url=settings.docling_remote_llm_url,
        headers=remote_llm_headers(settings),
        params=remote_llm_params(
            settings,
            model=(
                settings.docling_remote_llm_model
                or settings.docling_pdf_picture_description_model
            ),
            max_tokens=settings.docling_pdf_picture_description_max_new_tokens,
        ),
        timeout=settings.docling_remote_llm_timeout_seconds,
        concurrency=settings.docling_remote_llm_concurrency,
        prompt=settings.docling_pdf_picture_description_prompt,
        provenance=f"{settings.docling_pdf_picture_description_model} ({RUNTIME_REMOTE_LLM})",
    )


def build_vlm_convert_options(settings: Settings) -> Any:
    from docling.datamodel.pipeline_options_vlm_model import (
        ApiVlmOptions,
        ResponseFormat,
    )

    return ApiVlmOptions(
        prompt=settings.docling_vlm_prompt,
        scale=settings.docling_vlm_scale,
        temperature=settings.docling_remote_llm_temperature,
        url=settings.docling_remote_llm_url,
        headers=remote_llm_headers(settings),
        params=remote_llm_params(
            settings,
            model=settings.docling_remote_llm_model or settings.docling_vlm_model,
            max_tokens=settings.docling_remote_llm_max_tokens,
        ),
        timeout=settings.docling_remote_llm_timeout_seconds,
        concurrency=settings.docling_remote_llm_concurrency,
        response_format=ResponseFormat(settings.docling_vlm_response_format),
    )


def remote_llm_headers(settings: Settings) -> dict[str, str]:
    if settings.docling_remote_llm_api_key is None:
        return {}
    value = settings.docling_remote_llm_api_key
    if settings.docling_remote_llm_api_key_scheme:
        value = f"{settings.docling_remote_llm_api_key_scheme} {value}"
    return {settings.docling_remote_llm_api_key_header: value}


def remote_llm_params(
    settings: Settings,
    *,
    model: str,
    max_tokens: int,
) -> dict[str, Any]:
    return {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": settings.docling_remote_llm_temperature,
    }


def _validate_surya_transformers_compatibility(settings: Settings) -> None:
    if settings.docling_pdf_ocr_engine != "suryaocr":
        return

    transformers_version = _get_installed_distribution_version("transformers")
    if transformers_version is None:
        return

    major_version = _parse_major_version(transformers_version)
    if major_version is not None and major_version >= 5:
        raise RuntimeError(
            "SuryaOCR is not compatible with the installed Transformers version "
            f"{transformers_version}. Install the project pin with "
            '`python -m pip install --upgrade --force-reinstall "transformers>=4.57,<5"` '
            "and then rerun `python -m pip install -r requirements.txt`."
        )


def _get_installed_distribution_version(distribution_name: str) -> str | None:
    try:
        return version(distribution_name)
    except PackageNotFoundError:
        return None


def _parse_major_version(version_string: str) -> int | None:
    match = re.match(r"^(\d+)", version_string)
    if match is None:
        return None
    return int(match.group(1))
