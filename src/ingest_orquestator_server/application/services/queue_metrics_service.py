from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from ingest_orquestator_server.application.ports.ingestion_job_repository import (
    IngestionJobRepository,
)
from ingest_orquestator_server.application.services.parsed_document_dispatch_service import (
    ParsedDocumentDispatchService,
)
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.models.ingestion_job import IngestionJob
from ingest_orquestator_server.models.ingestion_status import IngestionStatus
from ingest_orquestator_server.models.queue_metrics import (
    DispatchQueueCounts,
    QueueJobSummary,
    QueueMetrics,
    QueueStageMetrics,
)


@dataclass(frozen=True)
class QueueStageDefinition:
    name: str
    statuses: tuple[IngestionStatus, ...]


QUEUE_STAGES = (
    QueueStageDefinition(
        "parser_queue",
        (IngestionStatus.PARSER_QUEUED, IngestionStatus.RETRYING),
    ),
    QueueStageDefinition("active_parser_jobs", (IngestionStatus.PARSING,)),
    QueueStageDefinition("dispatch_queue", (IngestionStatus.DISPATCH_QUEUED,)),
    QueueStageDefinition("dispatcher_workers", (IngestionStatus.DISPATCHING,)),
    QueueStageDefinition(
        "processed",
        (
            IngestionStatus.STORED_LOCAL,
            IngestionStatus.INDEXED_ELASTIC,
            IngestionStatus.COMPLETED,
        ),
    ),
    QueueStageDefinition(
        "failed",
        (IngestionStatus.RETRYABLE_FAILURE, IngestionStatus.FAILED),
    ),
)


class QueueMetricsService:
    def __init__(
        self,
        *,
        settings: Settings,
        job_repository: IngestionJobRepository,
        dispatch_service: ParsedDocumentDispatchService | None,
    ) -> None:
        self._settings = settings
        self._job_repository = job_repository
        self._dispatch_service = dispatch_service

    def metrics(self, *, recent_limit: int = 20) -> QueueMetrics:
        limit = max(1, min(recent_limit, 100))
        status_counts = self._job_repository.count_by_status()
        return QueueMetrics(
            queue_backend=self._settings.queue_backend,
            parser_queue_name=self._settings.dramatiq_parser_queue_name,
            dispatch_queue_name=self._settings.dramatiq_dispatch_queue_name,
            parser_process_count=self._settings.parser_process_count,
            parser_threads_per_process=self._settings.parser_threads_per_process,
            active_parser_job_count=status_counts.get(
                IngestionStatus.PARSING.value,
                0,
            ),
            queued_parser_job_count=(
                status_counts.get(IngestionStatus.PARSER_QUEUED.value, 0)
                + status_counts.get(IngestionStatus.RETRYING.value, 0)
            ),
            stale_parser_job_count=self._stale_parser_job_count(),
            parser_worker_count=self._settings.parser_worker_count,
            dispatch_worker_count=self._settings.dispatch_worker_count,
            status_counts=status_counts,
            stages=[
                self._stage_metrics(stage, status_counts=status_counts, limit=limit)
                for stage in QUEUE_STAGES
            ],
            dispatch_queue=self._dispatch_queue_counts(),
        )

    def _stage_metrics(
        self,
        stage: QueueStageDefinition,
        *,
        status_counts: dict[str, int],
        limit: int,
    ) -> QueueStageMetrics:
        statuses = {status.value for status in stage.statuses}
        return QueueStageMetrics(
            name=stage.name,
            statuses=list(stage.statuses),
            count=sum(status_counts.get(status, 0) for status in statuses),
            jobs=[
                self._job_summary(job)
                for job in self._job_repository.list_recent_by_status(statuses, limit=limit)
            ],
        )

    def _dispatch_queue_counts(self) -> DispatchQueueCounts | None:
        if self._dispatch_service is None:
            return None
        snapshot = self._dispatch_service.queue_status()
        return DispatchQueueCounts(
            max_bulk_size=snapshot.max_bulk_size,
            max_size=snapshot.max_size,
            max_payload_bytes=snapshot.max_payload_bytes,
            queued_count=snapshot.queued_count,
            in_flight_count=snapshot.in_flight_count,
            completed_count=snapshot.completed_count,
            failed_count=snapshot.failed_count,
        )

    def _stale_parser_job_count(self) -> int:
        timeout = timedelta(milliseconds=self._settings.dramatiq_parser_time_limit_ms)
        cutoff = datetime.now(UTC) - timeout
        stale_count = 0
        for job in self._job_repository.list_by_status(
            {IngestionStatus.PARSING.value}
        ):
            updated_at = job.updated_at
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=UTC)
            if updated_at < cutoff:
                stale_count += 1
        return stale_count

    @staticmethod
    def _job_summary(job: IngestionJob) -> QueueJobSummary:
        return QueueJobSummary(
            job_id=job.job_id,
            status=job.status,
            parser=job.parser,
            source_file_name=job.source_file_name,
            document_id=job.document_id,
            metadata=job.metadata,
            error=job.error,
            created_at=job.created_at,
            updated_at=job.updated_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
        )
