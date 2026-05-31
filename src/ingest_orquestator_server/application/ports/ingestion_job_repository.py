from __future__ import annotations

from typing import Protocol

from ingest_orquestator_server.models.ingestion_job import IngestionJob


class IngestionJobRepository(Protocol):
    def save(self, job: IngestionJob) -> None:
        """Create or update an ingestion job."""

    def get(self, job_id: str) -> IngestionJob | None:
        """Return a job by id, or None when it does not exist."""

    def list_active_job_ids(self) -> set[str]:
        """Return jobs that should be protected from cleanup."""

    def list_by_status(self, statuses: set[str]) -> list[IngestionJob]:
        """Return jobs with any of the requested status values."""
