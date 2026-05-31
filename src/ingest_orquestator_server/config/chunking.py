from __future__ import annotations

from ingest_orquestator_server.application.exceptions import UnsupportedIngestionOptionError

CHUNKING_STRATEGY_NAMES = {
    "hybrid",
    "line_based",
    "legacy_char",
}


def validate_chunking_strategy(strategy: str) -> str:
    selected_strategy = strategy.strip().lower()
    if selected_strategy not in CHUNKING_STRATEGY_NAMES:
        raise UnsupportedIngestionOptionError(
            "chunking_strategy must be one of hybrid, line_based, or legacy_char"
        )
    return selected_strategy
