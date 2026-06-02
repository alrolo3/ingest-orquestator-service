from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from ingest_orquestator_server.models.ingestion_document import (
    IngestionDocument,
    IngestionDocumentEnvelope,
    IngestionDocumentListResponse,
    IngestionRunSummary,
)
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
            self._save_run_snapshot(connection, job)

    def get(self, job_id: str) -> IngestionJob | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM ingestion_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return self._from_row(row)

    def upsert_document(
        self,
        *,
        content_hash: str,
        source_file_name: str | None,
        size_bytes: int | None,
        mime_type: str | None,
        storage_path: Path,
    ) -> IngestionDocument:
        now = datetime.now(UTC)
        document_id = str(uuid4())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO ingestion_documents (
                    document_id,
                    content_hash,
                    source_file_name,
                    size_bytes,
                    mime_type,
                    storage_path,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(content_hash) DO UPDATE SET
                    source_file_name = excluded.source_file_name,
                    size_bytes = excluded.size_bytes,
                    mime_type = excluded.mime_type,
                    storage_path = excluded.storage_path,
                    updated_at = excluded.updated_at
                """,
                (
                    document_id,
                    content_hash,
                    source_file_name,
                    size_bytes,
                    mime_type,
                    str(storage_path),
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
            row = connection.execute(
                "SELECT * FROM ingestion_documents WHERE content_hash = ?",
                (content_hash,),
            ).fetchone()
        return self._document_from_row(row)

    def create_run_for_job(self, job: IngestionJob, *, document_id: str) -> IngestionRunSummary:
        with self._connect() as connection:
            attempt_number = self._next_attempt_number(connection, document_id)
            connection.execute(
                """
                INSERT INTO ingestion_runs (
                    run_id,
                    job_id,
                    document_id,
                    attempt_number,
                    status,
                    parser,
                    pipeline,
                    source_file_name,
                    outputs_json,
                    metadata_json,
                    error,
                    created_at,
                    updated_at,
                    started_at,
                    completed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._run_row(job, document_id=document_id, attempt_number=attempt_number),
            )
            row = connection.execute(
                "SELECT * FROM ingestion_runs WHERE run_id = ?",
                (job.job_id,),
            ).fetchone()
        return self._run_from_row(row)

    def get_document(self, document_id: str) -> IngestionDocumentEnvelope | None:
        with self._connect() as connection:
            document_row = connection.execute(
                "SELECT * FROM ingestion_documents WHERE document_id = ?",
                (document_id,),
            ).fetchone()
            if document_row is None:
                return None
            run_rows = connection.execute(
                """
                SELECT * FROM ingestion_runs
                WHERE document_id = ?
                ORDER BY attempt_number DESC
                """,
                (document_id,),
            ).fetchall()
        return self._document_envelope_from_rows(document_row, run_rows)

    def get_document_storage_path(self, document_id: str) -> Path | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT storage_path FROM ingestion_documents WHERE document_id = ?",
                (document_id,),
            ).fetchone()
        if row is None:
            return None
        return Path(row["storage_path"])

    def list_documents(
        self,
        *,
        status: str | None = None,
        q: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> IngestionDocumentListResponse:
        offset = self._cursor_offset(cursor)
        bounded_limit = max(1, min(limit, 100))
        conditions: list[str] = []
        params: list[object] = []
        if q:
            conditions.append("(d.source_file_name LIKE ? OR d.content_hash LIKE ?)")
            params.extend([f"%{q}%", f"%{q}%"])
        if status:
            conditions.append(
                """
                EXISTS (
                    SELECT 1 FROM ingestion_runs latest
                    WHERE latest.document_id = d.document_id
                      AND latest.status = ?
                      AND latest.attempt_number = (
                        SELECT MAX(attempt_number)
                        FROM ingestion_runs
                        WHERE document_id = d.document_id
                      )
                )
                """
            )
            params.append(status)
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self._connect() as connection:
            total = int(
                connection.execute(
                    f"SELECT COUNT(*) AS count FROM ingestion_documents d {where_clause}",
                    tuple(params),
                ).fetchone()["count"]
            )
            document_rows = connection.execute(
                f"""
                SELECT d.* FROM ingestion_documents d
                {where_clause}
                ORDER BY d.updated_at DESC
                LIMIT ? OFFSET ?
                """,
                (*tuple(params), bounded_limit + 1, offset),
            ).fetchall()
            page_rows = document_rows[:bounded_limit]
            run_rows = self._runs_for_documents(
                connection,
                [str(row["document_id"]) for row in page_rows],
            )
        documents = [
            self._document_envelope_from_rows(
                document_row,
                run_rows.get(str(document_row["document_id"]), []),
            )
            for document_row in page_rows
        ]
        next_cursor = str(offset + bounded_limit) if len(document_rows) > bounded_limit else None
        return IngestionDocumentListResponse(
            documents=documents,
            next_cursor=next_cursor,
            total=total,
        )

    def list_runs(self, run_ids: list[str]) -> list[IngestionRunSummary]:
        if not run_ids:
            return []
        unique_run_ids = list(dict.fromkeys(run_ids))
        placeholders = ",".join("?" for _ in unique_run_ids)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM ingestion_runs WHERE run_id IN ({placeholders})",
                tuple(unique_run_ids),
            ).fetchall()
        by_id = {str(row["run_id"]): self._run_from_row(row) for row in rows}
        return [by_id[run_id] for run_id in unique_run_ids if run_id in by_id]

    def get_run(self, run_id: str) -> IngestionRunSummary | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM ingestion_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return self._run_from_row(row)

    def delete(self, job_id: str) -> IngestionJob | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM ingestion_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                "DELETE FROM ingestion_runs WHERE run_id = ?",
                (job_id,),
            )
            connection.execute(
                "DELETE FROM ingestion_jobs WHERE job_id = ?",
                (job_id,),
            )
        return self._from_row(row)

    def list_active_job_ids(self) -> set[str]:
        active_statuses = (
            IngestionStatus.PENDING.value,
            IngestionStatus.QUEUED.value,
            IngestionStatus.RUNNING.value,
            IngestionStatus.PARSER_QUEUED.value,
            IngestionStatus.PARSING.value,
            IngestionStatus.PARSED.value,
            IngestionStatus.DISPATCH_QUEUED.value,
            IngestionStatus.DISPATCHING.value,
            IngestionStatus.STORED_LOCAL.value,
            IngestionStatus.INDEXED_ELASTIC.value,
            IngestionStatus.RETRYABLE_FAILURE.value,
        )
        placeholders = ",".join("?" for _ in active_statuses)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT job_id FROM ingestion_jobs WHERE status IN ({placeholders})",
                active_statuses,
            ).fetchall()
        return {str(row["job_id"]) for row in rows}

    def list_by_status(self, statuses: set[str]) -> list[IngestionJob]:
        if not statuses:
            return []
        placeholders = ",".join("?" for _ in statuses)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM ingestion_jobs WHERE status IN ({placeholders})",
                tuple(statuses),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def count_by_status(self) -> dict[str, int]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT status, COUNT(*) AS count FROM ingestion_jobs GROUP BY status"
            ).fetchall()
        return {str(row["status"]): int(row["count"]) for row in rows}

    def list_recent_by_status(self, statuses: set[str], *, limit: int) -> list[IngestionJob]:
        if not statuses or limit <= 0:
            return []
        placeholders = ",".join("?" for _ in statuses)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM ingestion_jobs
                WHERE status IN ({placeholders})
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (*tuple(statuses), limit),
            ).fetchall()
        return [self._from_row(row) for row in rows]

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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS ingestion_documents (
                    document_id TEXT PRIMARY KEY,
                    content_hash TEXT NOT NULL UNIQUE,
                    source_file_name TEXT,
                    size_bytes INTEGER,
                    mime_type TEXT,
                    storage_path TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS ingestion_runs (
                    run_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL UNIQUE,
                    document_id TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    parser TEXT NOT NULL,
                    pipeline TEXT,
                    source_file_name TEXT,
                    outputs_json TEXT,
                    metadata_json TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    FOREIGN KEY(document_id) REFERENCES ingestion_documents(document_id)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_ingestion_documents_hash "
                "ON ingestion_documents(content_hash)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_ingestion_documents_updated "
                "ON ingestion_documents(updated_at)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_ingestion_runs_document "
                "ON ingestion_runs(document_id, attempt_number DESC)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_ingestion_runs_status_updated "
                "ON ingestion_runs(status, updated_at)"
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _next_attempt_number(connection: sqlite3.Connection, document_id: str) -> int:
        row = connection.execute(
            "SELECT COALESCE(MAX(attempt_number), 0) + 1 AS next_attempt "
            "FROM ingestion_runs WHERE document_id = ?",
            (document_id,),
        ).fetchone()
        return int(row["next_attempt"])

    def _save_run_snapshot(
        self,
        connection: sqlite3.Connection,
        job: IngestionJob,
    ) -> None:
        existing = connection.execute(
            "SELECT * FROM ingestion_runs WHERE run_id = ?",
            (job.job_id,),
        ).fetchone()
        if existing is None:
            return
        connection.execute(
            """
            UPDATE ingestion_runs SET
                document_id = ?,
                status = ?,
                parser = ?,
                pipeline = ?,
                source_file_name = ?,
                outputs_json = ?,
                metadata_json = ?,
                error = ?,
                created_at = ?,
                updated_at = ?,
                started_at = ?,
                completed_at = ?
            WHERE run_id = ?
            """,
            (
                job.document_id or str(existing["document_id"]),
                job.status.value,
                job.parser,
                self._job_pipeline(job),
                job.source_file_name,
                job.outputs.model_dump_json() if job.outputs is not None else None,
                json.dumps(job.metadata),
                job.error,
                job.created_at.isoformat(),
                job.updated_at.isoformat(),
                job.started_at.isoformat() if job.started_at is not None else None,
                job.completed_at.isoformat() if job.completed_at is not None else None,
                job.job_id,
            ),
        )

    def _runs_for_documents(
        self,
        connection: sqlite3.Connection,
        document_ids: list[str],
    ) -> dict[str, list[sqlite3.Row]]:
        if not document_ids:
            return {}
        placeholders = ",".join("?" for _ in document_ids)
        rows = connection.execute(
            f"""
            SELECT * FROM ingestion_runs
            WHERE document_id IN ({placeholders})
            ORDER BY document_id, attempt_number DESC
            """,
            tuple(document_ids),
        ).fetchall()
        grouped: dict[str, list[sqlite3.Row]] = {}
        for row in rows:
            grouped.setdefault(str(row["document_id"]), []).append(row)
        return grouped

    def _document_envelope_from_rows(
        self,
        document_row: sqlite3.Row,
        run_rows: list[sqlite3.Row],
    ) -> IngestionDocumentEnvelope:
        runs = [self._run_from_row(row) for row in run_rows]
        return IngestionDocumentEnvelope(
            document=self._document_from_row(document_row),
            latest_run=runs[0] if runs else None,
            runs=runs,
        )

    @staticmethod
    def _document_from_row(row: sqlite3.Row) -> IngestionDocument:
        return IngestionDocument(
            document_id=row["document_id"],
            content_hash=row["content_hash"],
            source_file_name=row["source_file_name"],
            size_bytes=row["size_bytes"],
            mime_type=row["mime_type"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _run_from_row(row: sqlite3.Row) -> IngestionRunSummary:
        outputs_json = row["outputs_json"]
        metadata_json = row["metadata_json"]
        run_id = str(row["run_id"])
        return IngestionRunSummary(
            run_id=run_id,
            job_id=row["job_id"],
            document_id=row["document_id"],
            attempt_number=int(row["attempt_number"]),
            status=IngestionStatus(row["status"]),
            parser=row["parser"],
            pipeline=row["pipeline"],
            source_file_name=row["source_file_name"],
            status_url=f"/v1/ingest/runs/{run_id}",
            outputs_url=f"/v1/ingest/runs/{run_id}/outputs",
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

    @staticmethod
    def _run_row(
        job: IngestionJob,
        *,
        document_id: str,
        attempt_number: int,
    ) -> tuple[object, ...]:
        return (
            job.job_id,
            job.job_id,
            document_id,
            attempt_number,
            job.status.value,
            job.parser,
            SqliteIngestionJobRepository._job_pipeline(job),
            job.source_file_name,
            job.outputs.model_dump_json() if job.outputs is not None else None,
            json.dumps(job.metadata),
            job.error,
            job.created_at.isoformat(),
            job.updated_at.isoformat(),
            job.started_at.isoformat() if job.started_at is not None else None,
            job.completed_at.isoformat() if job.completed_at is not None else None,
        )

    @staticmethod
    def _job_pipeline(job: IngestionJob) -> str | None:
        pipeline = job.metadata.get("pipeline") or job.metadata.get("requested_pipeline")
        return str(pipeline) if pipeline is not None else None

    @staticmethod
    def _cursor_offset(cursor: str | None) -> int:
        if cursor is None:
            return 0
        try:
            return max(0, int(cursor))
        except ValueError:
            return 0

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
