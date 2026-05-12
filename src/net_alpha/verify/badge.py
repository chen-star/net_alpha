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
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from net_alpha.verify.invariants import (
    InvariantResult,
    check_al1_allocation_sums_to_100,
    check_al2_leaderboard_weight,
    check_ov1_total_market_value,
    check_ov2_unrealized_consistency,
    check_ov3_realized_ytd,
    check_pl1_value_consistency,
    check_pl2_pnl_consistency,
    check_pl3_holding_period,
    check_xp1_cross_page,
)
from net_alpha.verify.tolerances import Severity, load_tolerances


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


@dataclass
class BadgeStatus:
    severity: Severity
    failed: list[InvariantResult] = field(default_factory=list)
    warned: list[InvariantResult] = field(default_factory=list)
    skipped: list[InvariantResult] = field(default_factory=list)
    page: str = ""
    _total: int = 0

    @property
    def passed_count(self) -> int:
        return self._total - len(self.failed) - len(self.warned) - len(self.skipped)

    def total(self) -> int:
        return self._total


def _aggregate(results: list[InvariantResult], page: str) -> BadgeStatus:
    failed = [r for r in results if r.severity == Severity.FAIL]
    warned = [r for r in results if r.severity == Severity.WARN]
    skipped = [r for r in results if r.detail.get("skipped")]
    if failed:
        sev = Severity.FAIL
    elif warned:
        sev = Severity.WARN
    else:
        sev = Severity.OK
    return BadgeStatus(
        severity=sev,
        failed=failed,
        warned=warned,
        skipped=skipped,
        page=page,
        _total=len(results),
    )


def run_inline(*, snapshot: Any, page: str, today: date | None = None) -> BadgeStatus:
    """Run all L1 invariants applicable to `page` and return a BadgeStatus.

    `page` is one of "overview" | "positions". The snapshot duck-types onto
    whatever the route already has prepared - see Tasks 10 and 11 for the
    adapter shape used in the real routes.
    """
    tol_cfg = load_tolerances()
    today = today or date.today()
    results: list[InvariantResult] = []

    if page == "overview":
        results.append(
            check_ov1_total_market_value(
                total_market_value=snapshot.total_market_value,
                lots=snapshot.lots,
                tol=tol_cfg.invariants,
            )
        )
        results.append(
            check_ov2_unrealized_consistency(
                total_market_value=snapshot.total_market_value,
                total_basis=snapshot.total_basis,
                unrealized_pl=snapshot.unrealized_pl,
                tol=tol_cfg.invariants,
            )
        )
        results.append(
            check_ov3_realized_ytd(
                realized_pl_ytd=snapshot.realized_pl_ytd,
                closed_lots_ytd=snapshot.closed_lots_ytd,
                tol=tol_cfg.invariants,
            )
        )
        results.append(
            check_al1_allocation_sums_to_100(
                allocation_rows=snapshot.allocation_rows,
                tol=tol_cfg.invariants,
            )
        )
        results.append(
            check_al2_leaderboard_weight(
                leaderboard_rows=snapshot.leaderboard_rows,
                total_market_value=snapshot.total_market_value,
                tol=tol_cfg.invariants,
            )
        )
        # Snapshot the overview total for XP-1 in /positions.
        snapshot_overview_total(default_cache(), total_market_value=snapshot.total_market_value)
        return _aggregate(results, page)

    if page == "positions":
        lot_dicts = [
            {
                "id": lot.id,
                "qty": lot.qty,
                "current_price": lot.current_price,
                "market_value": lot.market_value,
                "adjusted_basis": lot.adjusted_basis,
                "unrealized_pl": lot.unrealized_pl,
                "tacked_acquired_date": lot.tacked_acquired_date,
                "bucket": lot.bucket,
            }
            for lot in snapshot.lots
        ]
        results.extend(check_pl1_value_consistency(lot_rows=lot_dicts, tol=tol_cfg.invariants))
        results.extend(check_pl2_pnl_consistency(lot_rows=lot_dicts, tol=tol_cfg.invariants))
        results.extend(check_pl3_holding_period(lot_rows=lot_dicts, today=today))

        positions_sum = sum(lot.market_value for lot in snapshot.lots)
        results.append(
            check_xp1_cross_page(
                positions_sum=positions_sum,
                cached_overview_total=read_overview_total(default_cache(), max_age_seconds=60),
                tol=tol_cfg.invariants,
            )
        )
        return _aggregate(results, page)

    raise ValueError(f"unknown page: {page}")
