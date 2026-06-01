from __future__ import annotations

import os
import signal
from pathlib import Path
from shutil import rmtree

from ingest_orquestator_server.application.ports.ingestion_job_repository import (
    IngestionJobRepository,
)
from ingest_orquestator_server.application.services.parsed_document_dispatch_queue_service import (
    ParsedDocumentDispatchQueueService,
)
from ingest_orquestator_server.config.settings import Settings
from ingest_orquestator_server.models.ingestion_job import IngestionJob
from ingest_orquestator_server.models.ingestion_status import IngestionStatus
from ingest_orquestator_server.models.job_removal import JobRemovalResult
from ingest_orquestator_server.models.output_files import OutputFiles


class JobRemovalService:
    def __init__(
        self,
        *,
        settings: Settings,
        job_repository: IngestionJobRepository,
        dispatch_queue_service: ParsedDocumentDispatchQueueService | None = None,
    ) -> None:
        self._settings = settings
        self._job_repository = job_repository
        self._dispatch_queue_service = dispatch_queue_service

    def remove_job(self, job_id: str) -> JobRemovalResult | None:
        job = self._job_repository.get(job_id)
        if job is None:
            return None

        terminated, signal_number, process_error = self._terminate_parser_process(job)
        removed_dispatch_queue_item = (
            self._dispatch_queue_service.remove_by_job_id(job_id)
            if self._dispatch_queue_service is not None
            else False
        )
        removed_artifact_count = self._remove_artifacts(job)
        deleted = self._job_repository.delete(job_id)
        if deleted is None:
            return None

        return JobRemovalResult(
            job_id=job.job_id,
            previous_status=job.status,
            parser_process_terminated=terminated,
            parser_process_signal=signal_number,
            parser_process_error=process_error,
            removed_dispatch_queue_item=removed_dispatch_queue_item,
            removed_artifact_count=removed_artifact_count,
        )

    def _terminate_parser_process(
        self,
        job: IngestionJob,
    ) -> tuple[bool, int | None, str | None]:
        if job.status != IngestionStatus.PARSING:
            return False, None, None
        pid = _parser_runtime_pid(job)
        if pid is None:
            return False, None, "No parser process id is recorded for this job."
        if pid == os.getpid():
            return False, None, "Refusing to terminate the API process."

        signal_number = signal.SIGTERM
        try:
            os.kill(pid, signal_number)
        except ProcessLookupError:
            return False, signal_number, "Parser process is no longer running."
        except PermissionError as exc:
            return False, signal_number, str(exc)
        return True, signal_number, None

    def _remove_artifacts(self, job: IngestionJob) -> int:
        removed_count = 0
        for path in self._artifact_paths(job):
            if not self._is_removable_artifact(path):
                continue
            if path.is_dir():
                rmtree(path)
                removed_count += 1
            elif path.exists():
                path.unlink()
                removed_count += 1
        return removed_count

    def _artifact_paths(self, job: IngestionJob) -> list[Path]:
        paths: list[Path] = []
        if job.input_path is not None:
            paths.append(job.input_path)
        if job.outputs is None:
            return _dedupe_paths(paths)

        output_dir = job.outputs.output_dir
        paths.append(output_dir)
        output_dir_resolved = output_dir.resolve(strict=False)
        for path in _output_file_paths(job.outputs):
            if path.resolve(strict=False).is_relative_to(output_dir_resolved):
                continue
            paths.append(path)
        return _dedupe_paths(paths)

    def _is_removable_artifact(self, path: Path) -> bool:
        if not path.exists():
            return False
        resolved = path.resolve()
        removable_roots = (
            self._settings.uploads_dir.resolve(),
            self._settings.outputs_dir.resolve(),
        )
        return any(resolved != root and resolved.is_relative_to(root) for root in removable_roots)


def _parser_runtime_pid(job: IngestionJob) -> int | None:
    runtime = job.metadata.get("parser_runtime")
    if not isinstance(runtime, dict):
        return None
    pid = runtime.get("pid")
    if isinstance(pid, int) and pid > 0:
        return pid
    return None


def _output_file_paths(outputs: OutputFiles) -> list[Path]:
    return [
        path
        for key, path in outputs
        if key != "output_dir" and isinstance(path, Path)
    ]


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    deduped: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve(strict=False)
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(path)
    return deduped
