from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ingest_orquestator_server.models.ingestion_document import (
    IngestionDocument,
    IngestionDocumentEnvelope,
    IngestionDocumentListResponse,
    IngestionRunSummary,
)
from ingest_orquestator_server.models.ingestion_job import IngestionJob


class IngestionJobRepository(Protocol):
    def save(self, job: IngestionJob) -> None:
        """Create or update an ingestion job."""

    def get(self, job_id: str) -> IngestionJob | None:
        """Return a job by id, or None when it does not exist."""

    def delete(self, job_id: str) -> IngestionJob | None:
        """Delete and return a job by id, or None when it does not exist."""

    def list_active_job_ids(self) -> set[str]:
        """Return jobs that should be protected from cleanup."""

    def list_by_status(self, statuses: set[str]) -> list[IngestionJob]:
        """Return jobs with any of the requested status values."""

    def count_by_status(self) -> dict[str, int]:
        """Return persisted job counts grouped by status value."""

    def list_recent_by_status(self, statuses: set[str], *, limit: int) -> list[IngestionJob]:
        """Return recent jobs with any of the requested status values."""

    def upsert_document(
        self,
        *,
        content_hash: str,
        source_file_name: str | None,
        size_bytes: int | None,
        mime_type: str | None,
        storage_path: Path,
    ) -> IngestionDocument:
        """Create or update a stable document row for uploaded content."""

    def create_run_for_job(self, job: IngestionJob, *, document_id: str) -> IngestionRunSummary:
        """Create a document run row for a legacy job."""

    def get_document(self, document_id: str) -> IngestionDocumentEnvelope | None:
        """Return a document envelope, or None when it does not exist."""

    def get_document_storage_path(self, document_id: str) -> Path | None:
        """Return the stored upload path for a document."""

    def list_documents(
        self,
        *,
        status: str | None = None,
        q: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> IngestionDocumentListResponse:
        """Return a bounded page of document envelopes."""

    def list_runs(self, run_ids: list[str]) -> list[IngestionRunSummary]:
        """Return run summaries for requested ids."""

    def get_run(self, run_id: str) -> IngestionRunSummary | None:
        """Return a run summary, or None when it does not exist."""
