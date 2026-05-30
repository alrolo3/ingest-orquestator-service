from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from shutil import rmtree

from ingest_orquestator_server.application.ports.ingestion_job_repository import (
    IngestionJobRepository,
)
from ingest_orquestator_server.config.settings import Settings


@dataclass(frozen=True)
class CleanupResult:
    dry_run: bool
    cutoff: datetime
    deleted_paths: list[Path]
    skipped_paths: list[Path]


class StorageCleanupService:
    def __init__(
        self,
        *,
        settings: Settings,
        job_repository: IngestionJobRepository,
    ) -> None:
        self._settings = settings
        self._job_repository = job_repository

    def cleanup(self, *, older_than_days: int | None = None, dry_run: bool = True) -> CleanupResult:
        days = older_than_days or self._settings.retention_days
        cutoff = datetime.now(UTC) - timedelta(days=days)
        protected_job_ids = self._job_repository.list_active_job_ids()
        candidates = [
            *self._iter_children(self._settings.uploads_dir),
            *self._iter_children(self._settings.outputs_dir),
        ]

        deleted_paths: list[Path] = []
        skipped_paths: list[Path] = []
        for path in candidates:
            if self._is_protected(path, protected_job_ids) or not self._is_older_than(path, cutoff):
                skipped_paths.append(path)
                continue
            deleted_paths.append(path)
            if not dry_run:
                if path.is_dir():
                    rmtree(path)
                elif path.exists():
                    path.unlink()

        return CleanupResult(
            dry_run=dry_run,
            cutoff=cutoff,
            deleted_paths=deleted_paths,
            skipped_paths=skipped_paths,
        )

    @staticmethod
    def _iter_children(path: Path) -> list[Path]:
        if not path.exists():
            return []
        return list(path.iterdir())

    @staticmethod
    def _is_protected(path: Path, protected_job_ids: set[str]) -> bool:
        return any(path.name.startswith(job_id) for job_id in protected_job_ids)

    @staticmethod
    def _is_older_than(path: Path, cutoff: datetime) -> bool:
        modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        return modified_at < cutoff
