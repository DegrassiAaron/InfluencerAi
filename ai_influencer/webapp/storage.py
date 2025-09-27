"""Simple storage helpers for managing application data records."""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS data_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class StorageError(RuntimeError):
    """Raised when the storage backend cannot be initialised."""


def _get_db_path() -> Path:
    raw_path = os.environ.get("DATA_DB_PATH")
    if not raw_path:
        raise StorageError("DATA_DB_PATH environment variable is not configured")
    path = Path(raw_path).expanduser().resolve()
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    return path


def create_connection() -> sqlite3.Connection:
    """Create and return an initialised SQLite connection."""

    path = _get_db_path()
    connection = sqlite3.connect(path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    _initialise_schema(connection)
    return connection


def _initialise_schema(connection: sqlite3.Connection) -> None:
    with connection:
        connection.executescript(SCHEMA)


def list_records(connection: sqlite3.Connection) -> list[Dict[str, Any]]:
    cursor = connection.execute(
        "SELECT id, name, value, updated_at FROM data_records ORDER BY id ASC"
    )
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


def _fetch_record(connection: sqlite3.Connection, record_id: int) -> Dict[str, Any]:
    cursor = connection.execute(
        "SELECT id, name, value, updated_at FROM data_records WHERE id = ?",
        (record_id,),
    )
    row = cursor.fetchone()
    if row is None:
        raise KeyError(record_id)
    return dict(row)


def update_record(
    connection: sqlite3.Connection,
    *,
    name: str,
    value: str,
    record_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Insert a new record or update an existing one."""

    timestamp = datetime.now(timezone.utc).isoformat()
    if record_id is None:
        cursor = connection.execute(
            "INSERT INTO data_records (name, value, updated_at) VALUES (?, ?, ?)",
            (name, value, timestamp),
        )
        new_id = cursor.lastrowid
        connection.commit()
        return _fetch_record(connection, int(new_id))

    cursor = connection.execute(
        "UPDATE data_records SET name = ?, value = ?, updated_at = ? WHERE id = ?",
        (name, value, timestamp, record_id),
    )
    if cursor.rowcount == 0:
        try:
            _fetch_record(connection, record_id)
        except KeyError:
            connection.rollback()
            raise
        connection.commit()
        return _fetch_record(connection, record_id)
    connection.commit()
    return _fetch_record(connection, record_id)


def delete_record(connection: sqlite3.Connection, record_id: int) -> None:
    cursor = connection.execute(
        "DELETE FROM data_records WHERE id = ?",
        (record_id,),
    )
    if cursor.rowcount == 0:
        connection.rollback()
        raise KeyError(record_id)
    connection.commit()
