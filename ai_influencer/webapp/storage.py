"""SQLite backed storage utilities for the web application."""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


SCHEMA = """
CREATE TABLE IF NOT EXISTS data_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    payload TEXT NOT NULL
);
"""


def _initialize_schema(connection: sqlite3.Connection) -> None:
    """Ensure the database schema exists for the storage layer."""

    with connection:  # Runs inside a transaction
        connection.execute(SCHEMA)


def _row_to_dict(row: sqlite3.Row) -> Dict[str, object]:
    """Convert a sqlite row to the public dictionary representation."""

    payload = json.loads(row["payload"]) if row["payload"] else {}
    return {"id": row["id"], "name": row["name"], "payload": payload}


def _validate_identifier(identifier: object) -> int:
    if not isinstance(identifier, int):
        raise TypeError("Identifier must be an integer")
    if identifier <= 0:
        raise ValueError("Identifier must be a positive integer")
    return identifier


def _validate_name(name: object) -> str:
    if not isinstance(name, str):
        raise TypeError("'name' must be a string")
    stripped = name.strip()
    if not stripped:
        raise ValueError("'name' must not be empty")
    return stripped


def _validate_payload(payload: object) -> Dict[str, object]:
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise TypeError("'payload' must be a dictionary if provided")
    return payload


@dataclass
class Storage:
    """Context manager wrapper around a SQLite connection."""

    connection: sqlite3.Connection

    def __post_init__(self) -> None:
        self.connection.row_factory = sqlite3.Row
        _initialize_schema(self.connection)

    def __enter__(self) -> "Storage":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.connection.close()

    # CRUD operations -----------------------------------------------------
    def list_data(self) -> List[Dict[str, object]]:
        cursor = self.connection.execute(
            "SELECT id, name, payload FROM data_entries ORDER BY id ASC"
        )
        return [_row_to_dict(row) for row in cursor.fetchall()]

    def get_data(self, identifier: object) -> Optional[Dict[str, object]]:
        data_id = _validate_identifier(identifier)
        cursor = self.connection.execute(
            "SELECT id, name, payload FROM data_entries WHERE id = ?",
            (data_id,),
        )
        row = cursor.fetchone()
        return _row_to_dict(row) if row else None

    def create_data(self, data: object) -> Dict[str, object]:
        if not isinstance(data, dict):
            raise TypeError("Payload must be a dictionary")

        name = _validate_name(data.get("name"))
        payload = json.dumps(_validate_payload(data.get("payload")))

        cursor = self.connection.execute(
            "INSERT INTO data_entries (name, payload) VALUES (?, ?)",
            (name, payload),
        )
        self.connection.commit()
        return self.get_data(cursor.lastrowid)

    def update_data(self, identifier: object, data: object) -> Dict[str, object]:
        data_id = _validate_identifier(identifier)
        if not isinstance(data, dict):
            raise TypeError("Payload must be a dictionary")

        updates: List[str] = []
        params: List[object] = []

        if "name" in data:
            updates.append("name = ?")
            params.append(_validate_name(data["name"]))

        if "payload" in data:
            updates.append("payload = ?")
            params.append(json.dumps(_validate_payload(data["payload"])))

        if not updates:
            raise ValueError("No valid fields to update")

        params.append(data_id)
        cursor = self.connection.execute(
            f"UPDATE data_entries SET {', '.join(updates)} WHERE id = ?",
            tuple(params),
        )
        if cursor.rowcount == 0:
            raise KeyError(f"Data entry with id {data_id} does not exist")

        self.connection.commit()
        updated = self.get_data(data_id)
        if updated is None:
            raise KeyError(f"Data entry with id {data_id} does not exist")
        return updated

    def delete_data(self, identifier: object) -> bool:
        data_id = _validate_identifier(identifier)
        cursor = self.connection.execute(
            "DELETE FROM data_entries WHERE id = ?",
            (data_id,),
        )
        self.connection.commit()
        return cursor.rowcount > 0


def get_storage() -> Storage:
    """Return a Storage context manager connected to the configured database."""

    db_path_env = os.environ.get("DATA_DB_PATH")
    if db_path_env:
        path = Path(db_path_env).expanduser()
    else:
        base_dir = Path(__file__).resolve().parent
        path = base_dir / "data.db"

    if path != Path(":memory:"):
        path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(str(path), check_same_thread=False)
    return Storage(connection)

