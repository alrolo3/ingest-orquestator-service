from __future__ import annotations

from ingest_orquestator_server.application.exceptions import JobNotFoundError
from ingest_orquestator_server.application.ports.ingestion_job_repository import (
    IngestionJobRepository,
)
from ingest_orquestator_server.models.ingestion_document import (
    IngestionDocumentEnvelope,
    IngestionDocumentListResponse,
    IngestionRunSummary,
)


class DocumentRunQueryService:
    def __init__(self, job_repository: IngestionJobRepository) -> None:
        self._job_repository = job_repository

    def get_document(self, document_id: str) -> IngestionDocumentEnvelope:
        document = self._job_repository.get_document(document_id)
        if document is None:
            raise JobNotFoundError(document_id)
        return document

    def list_documents(
        self,
        *,
        status: str | None = None,
        q: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> IngestionDocumentListResponse:
        return self._job_repository.list_documents(
            status=status,
            q=q,
            limit=limit,
            cursor=cursor,
        )

    def get_run(self, run_id: str) -> IngestionRunSummary:
        run = self._job_repository.get_run(run_id)
        if run is None:
            raise JobNotFoundError(run_id)
        return run

    def list_runs(self, run_ids: list[str]) -> list[IngestionRunSummary]:
        return self._job_repository.list_runs(run_ids)
