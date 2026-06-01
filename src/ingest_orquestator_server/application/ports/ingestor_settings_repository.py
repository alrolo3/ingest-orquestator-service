from typing import Protocol


class IngestorSettingsRepository(Protocol):
    def list(self) -> dict[str, object]:
        """Return persisted setting overrides keyed by settings field name."""

    def set(self, key: str, value: object) -> None:
        """Persist one setting override."""

    def delete(self, key: str) -> None:
        """Remove one persisted setting override."""
