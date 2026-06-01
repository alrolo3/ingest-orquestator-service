import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


class SqliteIngestorSettingsRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def list(self) -> dict[str, object]:
        with self._connect() as connection:
            rows = connection.execute("SELECT key, value_json FROM ingestor_settings").fetchall()
        return {str(row["key"]): json.loads(row["value_json"]) for row in rows}

    def set(self, key: str, value: object) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO ingestor_settings (key, value_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = excluded.updated_at
                """,
                (key, json.dumps(value), datetime.now(UTC).isoformat()),
            )

    def delete(self, key: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM ingestor_settings WHERE key = ?", (key,))

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS ingestor_settings (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        return connection
