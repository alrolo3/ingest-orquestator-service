from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, Field


class ChunkingStrategy(StrEnum):
    TOKEN = "token"
    PAGE = "page"
    LINE = "line"


_LEGACY_STRATEGY_ALIASES = {
    "hybrid": ChunkingStrategy.TOKEN,
    "line_based": ChunkingStrategy.LINE,
}


def normalize_chunking_strategy(strategy: str | ChunkingStrategy) -> ChunkingStrategy:
    if isinstance(strategy, ChunkingStrategy):
        return strategy
    selected_strategy = strategy.strip().lower()
    if selected_strategy in _LEGACY_STRATEGY_ALIASES:
        return _LEGACY_STRATEGY_ALIASES[selected_strategy]
    try:
        return ChunkingStrategy(selected_strategy)
    except ValueError as exc:
        supported = ", ".join(strategy.value for strategy in ChunkingStrategy)
        raise ValueError(f"chunking_strategy must be one of {supported}") from exc


class ChunkingStrategyCapability(BaseModel):
    value: ChunkingStrategy
    label: str
    default: bool = False


class ParserChunkingCapabilities(BaseModel):
    enabled: bool = True
    default_strategy: ChunkingStrategy | None = None
    strategies: list[ChunkingStrategyCapability] = Field(default_factory=list)

    def supports(self, strategy: ChunkingStrategy) -> bool:
        return any(capability.value == strategy for capability in self.strategies)


@dataclass(frozen=True)
class ChunkingSelection:
    enabled: bool
    strategy: ChunkingStrategy | None

    def metadata(self) -> dict[str, object]:
        return {
            "chunking_enabled": self.enabled,
            "chunking_strategy": self.strategy.value
            if self.enabled and self.strategy is not None
            else None,
        }
