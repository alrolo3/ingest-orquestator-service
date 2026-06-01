from __future__ import annotations

from ingest_orquestator_server.application.exceptions import UnsupportedIngestionOptionError
from ingest_orquestator_server.models.chunking import (
    ChunkingStrategy,
    normalize_chunking_strategy,
)

CHUNKING_STRATEGY_NAMES = {strategy.value for strategy in ChunkingStrategy}


def validate_chunking_strategy(strategy: str) -> str:
    try:
        return normalize_chunking_strategy(strategy).value
    except ValueError as exc:
        raise UnsupportedIngestionOptionError(str(exc)) from exc
