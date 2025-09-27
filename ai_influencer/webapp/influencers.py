"""In-memory persistence layer for influencer metadata."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Dict, Optional


class InfluencerAlreadyExistsError(Exception):
    """Raised when attempting to create a duplicated influencer."""


@dataclass
class StoredInfluencer:
    """Represents the persisted state of an influencer."""

    handle: str
    identifier: str
    story: str
    personality: str
    created_at: datetime


def extract_handle(identifier: str) -> str:
    """Normalize an arbitrary identifier into a bare handle."""

    handle = identifier.strip()
    handle = handle.lstrip("@")
    if "/" in handle:
        handle = handle.rstrip("/").split("/")[-1]
    return handle


class InfluencerStore:
    """Simple thread-safe in-memory store for influencers."""

    def __init__(self) -> None:
        self._items: Dict[str, StoredInfluencer] = {}
        self._lock = Lock()

    def _key_for(self, identifier: str) -> str:
        return extract_handle(identifier).lower()

    def create(
        self, *, identifier: str, story: str, personality: str
    ) -> StoredInfluencer:
        handle = extract_handle(identifier)
        if not handle:
            raise ValueError("Identifier is required")
        key = handle.lower()
        normalized_story = story.strip()
        normalized_personality = personality.strip()
        with self._lock:
            if key in self._items:
                raise InfluencerAlreadyExistsError(handle)
            record = StoredInfluencer(
                handle=f"@{handle}",
                identifier=handle,
                story=normalized_story,
                personality=normalized_personality,
                created_at=datetime.now(timezone.utc),
            )
            self._items[key] = record
        return record

    def get(self, identifier: str) -> Optional[StoredInfluencer]:
        key = self._key_for(identifier)
        if not key:
            return None
        return self._items.get(key)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


_store = InfluencerStore()


def get_influencer_store() -> InfluencerStore:
    """Return the singleton influencer store instance."""

    return _store


__all__ = [
    "InfluencerAlreadyExistsError",
    "InfluencerStore",
    "StoredInfluencer",
    "extract_handle",
    "get_influencer_store",
]
