from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock
from typing import Any

from ingest_orquestator_server.application.ports.ingestion_job_repository import (
    IngestionJobRepository,
)
from ingest_orquestator_server.application.services.stage_logger import log_stage
from ingest_orquestator_server.models.parse_progress import ParseProgressUpdate


class JobProgressReporter:
    def __init__(
        self,
        *,
        job_repository: IngestionJobRepository,
        history_limit: int,
    ) -> None:
        self._job_repository = job_repository
        self._history_limit = history_limit
        self._lock = Lock()

    def callback_for(self, job_id: str):
        def _callback(update: ParseProgressUpdate) -> None:
            self.report(job_id, update)

        return _callback

    def report(self, job_id: str, update: ParseProgressUpdate) -> None:
        payload = self._payload(update)
        log_stage("ingestion.progress", job_id=job_id, **payload)

        with self._lock:
            job = self._job_repository.get(job_id)
            if job is None:
                return
            metadata = dict(job.metadata)
            history = list(metadata.get("progress_history") or [])
            history.append(payload)
            metadata["progress"] = payload
            metadata["progress_history"] = history[-self._history_limit :]
            self._job_repository.save(
                job.model_copy(
                    update={
                        "metadata": metadata,
                        "updated_at": datetime.now(UTC),
                    }
                )
            )

    @staticmethod
    def _payload(update: ParseProgressUpdate) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "component": update.component,
            "stage": update.stage,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        if update.message:
            payload["message"] = update.message
        if update.input_format is not None:
            payload["input_format"] = update.input_format
        if update.pipeline is not None:
            payload["pipeline"] = update.pipeline
        if update.page_count is not None:
            payload["page_count"] = update.page_count
        if update.pages_completed is not None:
            payload["pages_completed"] = update.pages_completed
        if update.current_page is not None:
            payload["current_page"] = update.current_page
        if update.page_count is not None and update.pages_completed is not None:
            payload["pages_remaining"] = max(update.page_count - update.pages_completed, 0)
            payload["percent_complete"] = (
                round((update.pages_completed / update.page_count) * 100, 2)
                if update.page_count > 0
                else 100.0
            )
        if update.details:
            payload["details"] = dict(update.details)
        return payload
