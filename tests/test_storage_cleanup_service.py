import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ingest_orquestator_server.application.services.storage_cleanup_service import (
    StorageCleanupService,
)
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.infrastructure.sqlite.sqlite_ingestion_job_repository import (
    SqliteIngestionJobRepository,
)
from ingest_orquestator_server.models.ingestion_job import IngestionJob
from ingest_orquestator_server.models.ingestion_status import IngestionStatus


def test_cleanup_dry_run_lists_old_artifacts(tmp_path: Path) -> None:
    settings = Settings(storage_dir=tmp_path)
    repository = SqliteIngestionJobRepository(settings.jobs_db_path)
    old_output = settings.outputs_dir / "old-job"
    old_output.mkdir(parents=True)
    old_time = (datetime.now(UTC) - timedelta(days=40)).timestamp()
    os.utime(old_output, (old_time, old_time))

    result = StorageCleanupService(settings=settings, job_repository=repository).cleanup(
        older_than_days=30,
        dry_run=True,
    )

    assert old_output in result.deleted_paths
    assert old_output.exists()


def test_cleanup_skips_active_jobs(tmp_path: Path) -> None:
    settings = Settings(storage_dir=tmp_path)
    repository = SqliteIngestionJobRepository(settings.jobs_db_path)
    repository.save(IngestionJob(job_id="active", status=IngestionStatus.RUNNING, parser="docling"))
    active_output = settings.outputs_dir / "active"
    active_output.mkdir(parents=True)
    old_time = (datetime.now(UTC) - timedelta(days=40)).timestamp()
    os.utime(active_output, (old_time, old_time))

    result = StorageCleanupService(settings=settings, job_repository=repository).cleanup(
        older_than_days=30,
        dry_run=False,
    )

    assert active_output in result.skipped_paths
    assert active_output.exists()
