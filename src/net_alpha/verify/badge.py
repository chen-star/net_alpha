"""L1 render-time orchestrator.

This module hosts:
  - the BadgeStatus dataclass (the inline chip's payload)
  - run_inline(): the entrypoint each route calls before rendering
  - OverviewTotalCache: a tiny module-level cache for the XP-1 cross-page check

The cache is intentionally a single-process dict - this app runs one user on
one local FastAPI process, so there's no session/multi-tenant concern.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class OverviewTotalCache:
    """Holds the latest Overview total_market_value so /positions can compare."""

    total: float | None = None
    written_at: float | None = None  # monotonic seconds


# Module-level singleton - created once per process. Tests construct a fresh
# instance and pass it explicitly via the public helpers below.
_default = OverviewTotalCache()


def default_cache() -> OverviewTotalCache:
    return _default


def snapshot_overview_total(
    cache: OverviewTotalCache,
    *,
    total_market_value: float,
    _now: Callable[[], float] = time.monotonic,
) -> None:
    cache.total = total_market_value
    cache.written_at = _now()


def read_overview_total(
    cache: OverviewTotalCache,
    *,
    max_age_seconds: float,
    _now: Callable[[], float] = time.monotonic,
) -> float | None:
    if cache.total is None or cache.written_at is None:
        return None
    if _now() - cache.written_at > max_age_seconds:
        return None
    return cache.total
