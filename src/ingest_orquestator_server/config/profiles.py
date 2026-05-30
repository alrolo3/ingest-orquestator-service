from __future__ import annotations

from typing import Any

from ingest_orquestator_server.application.exceptions import UnsupportedIngestionOptionError
from ingest_orquestator_server.config.settings import Settings

PROFILE_NAMES = {
    "parse_only",
    "rag_ready",
    "ocr_only",
    "standard_enriched",
    "vlm",
}

CHUNKING_STRATEGY_NAMES = {
    "hybrid",
    "line_based",
    "legacy_char",
}


def resolve_profile_settings(
    settings: Settings,
    *,
    profile: str | None = None,
) -> Settings:
    selected_profile = validate_profile_name(profile or settings.profile)

    updates: dict[str, Any] = {"profile": selected_profile}
    if selected_profile == "parse_only":
        updates |= {
            "chunking_enabled": False,
            "embedding_output_enabled": False,
            "confidence_output_enabled": False,
        }
    elif selected_profile == "rag_ready":
        updates |= {
            "chunking_enabled": True,
            "chunking_strategy": "hybrid",
            "embedding_output_enabled": True,
            "confidence_output_enabled": True,
        }
    elif selected_profile == "ocr_only":
        updates |= {
            "docling_pipeline": "standard",
            "docling_pdf_do_ocr": True,
            "docling_pdf_do_table_structure": False,
            "docling_pdf_do_picture_classification": False,
            "docling_pdf_do_picture_description": False,
            "docling_pdf_do_code_enrichment": False,
            "docling_pdf_do_formula_enrichment": False,
            "chunking_enabled": True,
            "chunking_strategy": "hybrid",
            "embedding_output_enabled": True,
            "confidence_output_enabled": True,
        }
    elif selected_profile == "standard_enriched":
        updates |= {
            "docling_pipeline": "standard",
            "docling_pdf_do_ocr": True,
            "docling_pdf_do_table_structure": True,
            "docling_pdf_do_picture_classification": True,
            "docling_pdf_do_picture_description": True,
            "docling_pdf_do_code_enrichment": True,
            "docling_pdf_do_formula_enrichment": True,
            "chunking_enabled": True,
            "chunking_strategy": "hybrid",
            "embedding_output_enabled": True,
            "confidence_output_enabled": True,
        }
    elif selected_profile == "vlm":
        updates |= {
            "docling_pipeline": "vlm",
            "chunking_enabled": True,
            "chunking_strategy": "hybrid",
            "embedding_output_enabled": True,
            "confidence_output_enabled": True,
        }

    return settings.model_copy(update=updates)


def validate_profile_name(profile: str) -> str:
    selected_profile = profile.strip().lower()
    if selected_profile not in PROFILE_NAMES:
        raise UnsupportedIngestionOptionError(
            "profile must be one of parse_only, rag_ready, ocr_only, standard_enriched, or vlm"
        )
    return selected_profile


def validate_chunking_strategy(strategy: str) -> str:
    selected_strategy = strategy.strip().lower()
    if selected_strategy not in CHUNKING_STRATEGY_NAMES:
        raise UnsupportedIngestionOptionError(
            "chunking_strategy must be one of hybrid, line_based, or legacy_char"
        )
    return selected_strategy
