from __future__ import annotations

from ingest_orquestator_server.application.exceptions import JobNotFoundError
from ingest_orquestator_server.application.ports.ingestion_job_repository import (
    IngestionJobRepository,
)
from ingest_orquestator_server.models.ingestion_job import IngestionJob


class JobQueryService:
    def __init__(self, job_repository: IngestionJobRepository) -> None:
        self._job_repository = job_repository

    def get_job(self, job_id: str) -> IngestionJob:
        job = self._job_repository.get(job_id)
        if job is None:
            raise JobNotFoundError(job_id)
        return job

    def list_jobs(self, job_ids: list[str]) -> list[IngestionJob]:
        jobs: list[IngestionJob] = []
        seen: set[str] = set()
        for job_id in job_ids:
            if job_id in seen:
                continue
            seen.add(job_id)
            job = self._job_repository.get(job_id)
            if job is not None:
                jobs.append(job)
        return jobs
