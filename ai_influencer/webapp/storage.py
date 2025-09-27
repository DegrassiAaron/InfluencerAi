"""In-memory storage for demo data management endpoints."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, List, Optional


class DataStorage:
    """Thread-safe in-memory storage used by the data management API."""

    def __init__(self) -> None:
        self._items: Dict[int, Dict[str, Any]] = {}
        self._lock = Lock()
        self._next_id = 1

    def list(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [deepcopy(item) for item in self._items.values()]

    def create(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            item_id = self._next_id
            self._next_id += 1
            now = datetime.now(timezone.utc).isoformat()
            item = {
                "id": item_id,
                "name": payload.get("name"),
                "category": payload.get("category"),
                "description": payload.get("description"),
                "created_at": now,
                "updated_at": now,
            }
            self._items[item_id] = item
            return deepcopy(item)

    def get(self, data_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            item = self._items.get(data_id)
            return deepcopy(item) if item is not None else None

    def update(self, data_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            if data_id not in self._items:
                raise KeyError(data_id)
            now = datetime.now(timezone.utc).isoformat()
            stored = deepcopy(self._items[data_id])
            for key in ("name", "category", "description"):
                if key in payload:
                    stored[key] = payload[key]
            stored["updated_at"] = now
            self._items[data_id] = stored
            return deepcopy(stored)

    def delete(self, data_id: int) -> bool:
        with self._lock:
            if data_id not in self._items:
                return False
            del self._items[data_id]
            return True

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self._next_id = 1


_STORAGE = DataStorage()


def get_storage() -> DataStorage:
    """FastAPI dependency returning the shared storage instance."""

    return _STORAGE


def list_data(storage: DataStorage) -> List[Dict[str, Any]]:
    return storage.list()


def create_data(storage: DataStorage, payload: Dict[str, Any]) -> Dict[str, Any]:
    return storage.create(payload)


def get_data(storage: DataStorage, data_id: int) -> Optional[Dict[str, Any]]:
    return storage.get(data_id)


def update_data(storage: DataStorage, data_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    return storage.update(data_id, payload)


def delete_data(storage: DataStorage, data_id: int) -> bool:
    return storage.delete(data_id)
