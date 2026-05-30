from __future__ import annotations

import json
from typing import Annotated

import typer

from ingest_orquestator_server.application.services.storage_cleanup_service import (
    StorageCleanupService,
)
from ingest_orquestator_server.config.settings import get_settings
from ingest_orquestator_server.infrastructure.sqlite.sqlite_ingestion_job_repository import (
    SqliteIngestionJobRepository,
)


def cleanup(
    older_than_days: Annotated[
        int | None,
        typer.Option(
            "--older-than-days",
            help="Delete artifacts older than this many days. Defaults to INGEST_RETENTION_DAYS.",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run/--delete", help="Preview cleanup without deleting files."),
    ] = True,
) -> None:
    settings = get_settings()
    service = StorageCleanupService(
        settings=settings,
        job_repository=SqliteIngestionJobRepository(settings.jobs_db_path),
    )
    result = service.cleanup(older_than_days=older_than_days, dry_run=dry_run)
    typer.echo(
        json.dumps(
            {
                "dry_run": result.dry_run,
                "cutoff": result.cutoff.isoformat(),
                "deleted_paths": [str(path) for path in result.deleted_paths],
                "skipped_paths": [str(path) for path in result.skipped_paths],
            },
            indent=2,
        )
    )
