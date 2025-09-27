"""Simple in-memory storage utilities for the demo REST API."""
from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Dict, List, Optional


@dataclass
class _StorageState:
    """Internal state container guarded by a lock."""

    items: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    next_id: int = 1


class DataStorage:
    """Thread-safe in-memory storage for JSON-like payloads."""

    def __init__(self) -> None:
        self._state = _StorageState()
        self._lock = Lock()

    def list(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [item.copy() for item in self._state.items.values()]

    def get(self, item_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            item = self._state.items.get(item_id)
            return item.copy() if item is not None else None

    def create(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            item_id = self._state.next_id
            self._state.next_id += 1
            item = {"id": item_id, **payload}
            self._state.items[item_id] = item
            return item.copy()

    def update(self, item_id: int, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        with self._lock:
            if item_id not in self._state.items:
                return None
            updated = {"id": item_id, **payload}
            self._state.items[item_id] = updated
            return updated.copy()

    def delete(self, item_id: int) -> bool:
        with self._lock:
            return self._state.items.pop(item_id, None) is not None


_STORAGE = DataStorage()


def get_storage() -> DataStorage:
    """FastAPI dependency returning the shared storage instance."""

    return _STORAGE


def list_data(storage: DataStorage) -> List[Dict[str, Any]]:
    return storage.list()


def get_data(storage: DataStorage, item_id: int) -> Optional[Dict[str, Any]]:
    return storage.get(item_id)


def create_data(storage: DataStorage, payload: Dict[str, Any]) -> Dict[str, Any]:
    return storage.create(payload)


def update_data(
    storage: DataStorage, item_id: int, payload: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    return storage.update(item_id, payload)


def delete_data(storage: DataStorage, item_id: int) -> bool:
    return storage.delete(item_id)

