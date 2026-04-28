"""30-second TTL cache for the nav-bar issue count.

Module-level singleton (one process, one cache) is fine for a local
loopback-only app — no concurrency to worry about beyond FastAPI's
threadpool. Recomputing on every request would walk all_trades / all_lots
and that's wasteful.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from threading import Lock
from typing import TypeVar

T = TypeVar("T")


class BadgeCache:
    def __init__(self, ttl_seconds: float = 30.0):
        self._ttl = ttl_seconds
        self._lock = Lock()
        self._value: object | None = None
        self._expires_at: float = 0.0

    def get(self, compute: Callable[[], T]) -> T:
        now = time.monotonic()
        with self._lock:
            if self._value is None or now >= self._expires_at:
                self._value = compute()
                self._expires_at = now + self._ttl
            return self._value  # type: ignore[return-value]

    def invalidate(self) -> None:
        with self._lock:
            self._value = None
            self._expires_at = 0.0


# Module-level singleton.
_cache = BadgeCache(ttl_seconds=30.0)


def get_imports_badge_count(repo) -> int:
    """Count of issues that warrant a nav badge: ≥1 error or ≥3 warns."""
    from net_alpha.audit.hygiene import collect_issues

    def compute() -> int:
        issues = collect_issues(repo)
        errors = sum(1 for i in issues if i.severity == "error")
        warns = sum(1 for i in issues if i.severity == "warn")
        if errors >= 1 or warns >= 3:
            return errors + warns
        return 0

    return _cache.get(compute)
