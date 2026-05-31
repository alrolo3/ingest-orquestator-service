from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from ingest_orquestator_server.models.ingestion_job import IngestionJob
from ingest_orquestator_server.models.ingestion_status import IngestionStatus
from ingest_orquestator_server.models.output_files import OutputFiles


class SqliteIngestionJobRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def save(self, job: IngestionJob) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO ingestion_jobs (
                    job_id,
                    status,
                    parser,
                    source_file_name,
                    input_path,
                    document_id,
                    outputs_json,
                    metadata_json,
                    error,
                    created_at,
                    updated_at,
                    started_at,
                    completed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    status = excluded.status,
                    parser = excluded.parser,
                    source_file_name = excluded.source_file_name,
                    input_path = excluded.input_path,
                    document_id = excluded.document_id,
                    outputs_json = excluded.outputs_json,
                    metadata_json = excluded.metadata_json,
                    error = excluded.error,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    started_at = excluded.started_at,
                    completed_at = excluded.completed_at
                """,
                self._to_row(job),
            )

    def get(self, job_id: str) -> IngestionJob | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM ingestion_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return self._from_row(row)

    def list_active_job_ids(self) -> set[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT job_id FROM ingestion_jobs WHERE status IN (?, ?, ?, ?, ?, ?)",
                (
                    IngestionStatus.PENDING.value,
                    IngestionStatus.QUEUED.value,
                    IngestionStatus.RUNNING.value,
                    IngestionStatus.EMBEDDING_QUEUED.value,
                    IngestionStatus.SENT_TO_EMBEDDING_SYSTEM.value,
                    IngestionStatus.EMBEDDING_TASK_RUNNING.value,
                ),
            ).fetchall()
        return {str(row["job_id"]) for row in rows}

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS ingestion_jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    parser TEXT NOT NULL,
                    source_file_name TEXT,
                    input_path TEXT,
                    document_id TEXT,
                    outputs_json TEXT,
                    metadata_json TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT
                )
                """
            )
            columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(ingestion_jobs)").fetchall()
            }
            if "metadata_json" not in columns:
                connection.execute("ALTER TABLE ingestion_jobs ADD COLUMN metadata_json TEXT")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _to_row(job: IngestionJob) -> tuple[object, ...]:
        return (
            job.job_id,
            job.status.value,
            job.parser,
            job.source_file_name,
            str(job.input_path) if job.input_path is not None else None,
            job.document_id,
            job.outputs.model_dump_json() if job.outputs is not None else None,
            json.dumps(job.metadata),
            job.error,
            job.created_at.isoformat(),
            job.updated_at.isoformat(),
            job.started_at.isoformat() if job.started_at is not None else None,
            job.completed_at.isoformat() if job.completed_at is not None else None,
        )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> IngestionJob:
        outputs_json = row["outputs_json"]
        metadata_json = row["metadata_json"] if "metadata_json" in row.keys() else None
        return IngestionJob(
            job_id=row["job_id"],
            status=IngestionStatus(row["status"]),
            parser=row["parser"],
            source_file_name=row["source_file_name"],
            input_path=Path(row["input_path"]) if row["input_path"] else None,
            document_id=row["document_id"],
            outputs=OutputFiles.model_validate(json.loads(outputs_json)) if outputs_json else None,
            metadata=json.loads(metadata_json) if metadata_json else {},
            error=row["error"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            started_at=(datetime.fromisoformat(row["started_at"]) if row["started_at"] else None),
            completed_at=(
                datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None
            ),
        )
