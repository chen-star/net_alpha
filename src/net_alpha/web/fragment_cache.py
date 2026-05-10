"""In-process cache for the heavy compute behind HTMX fragments.

Cache key = (route_path, frozen request params, app.state.fragment_revision).
The revision counter is bumped by every write endpoint (trade CRUD, import
upload/delete, prefs save, splits/prices refresh); a 60s hard TTL is the
backstop in case a write path is missed.

Stores the rendered *context dict* — not HTML — so templates still render
each request and request-scoped Jinja globals (profile_switcher_data,
imports_badge_count, asset_v) keep working.
"""

from __future__ import annotations

import time
from threading import Lock
from typing import Any, Hashable


class FragmentCache:
    def __init__(self, ttl_seconds: int = 60, max_entries: int = 256) -> None:
        self._ttl = ttl_seconds
        self._max = max_entries
        self._store: dict[Hashable, tuple[float, Any]] = {}
        self._lock = Lock()

    def get(self, key: Hashable) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            ts, value = entry
            if time.monotonic() - ts > self._ttl:
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: Hashable, value: Any) -> None:
        with self._lock:
            if len(self._store) >= self._max and key not in self._store:
                # Drop the oldest entry to make room. Cheap LRU-ish eviction —
                # the store is small enough that a full scan is fine.
                oldest = min(self._store.items(), key=lambda kv: kv[1][0])[0]
                self._store.pop(oldest, None)
            self._store[key] = (time.monotonic(), value)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


def bump_fragment_revision(request_or_app) -> None:
    """Invalidate every cached fragment. Accepts a Request or a FastAPI app."""
    state = request_or_app.app.state if hasattr(request_or_app, "app") else request_or_app.state
    state.fragment_revision = getattr(state, "fragment_revision", 0) + 1
