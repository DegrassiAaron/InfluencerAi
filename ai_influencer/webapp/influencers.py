"""In-memory persistence layer for influencer metadata."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Dict, List, Optional


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
    lora_model: Optional[str] = None
    contents: Optional[List[str]] = field(default=None)


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
        self,
        *,
        identifier: str,
        story: str,
        personality: str,
        lora_model: Optional[str] = None,
        contents: Optional[List[str]] = None,
    ) -> StoredInfluencer:
        handle = extract_handle(identifier)
        if not handle:
            raise ValueError("Identifier is required")
        key = handle.lower()
        normalized_story = story.strip()
        normalized_personality = personality.strip()
        normalized_lora = self._normalize_lora(lora_model)
        normalized_contents = self._normalize_contents(contents)
        with self._lock:
            if key in self._items:
                raise InfluencerAlreadyExistsError(handle)
            record = StoredInfluencer(
                handle=f"@{handle}",
                identifier=handle,
                story=normalized_story,
                personality=normalized_personality,
                created_at=datetime.now(timezone.utc),
                lora_model=normalized_lora,
                contents=normalized_contents,
            )
            self._items[key] = record
        return record

    def _normalize_lora(self, lora_model: Optional[str]) -> Optional[str]:
        if lora_model is None:
            return None
        candidate = lora_model.strip()
        return candidate or None

    def _normalize_contents(
        self, contents: Optional[List[str]]
    ) -> Optional[List[str]]:
        if not contents:
            return None
        normalized = [item.strip() for item in contents if item and item.strip()]
        return normalized or None

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
