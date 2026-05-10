"""diff_plan: pure function over current Plan rows + snapshot rows.

Rules (per spec §4.3):
- ticker in current, not in snapshot           → "new"
- risk_pill tier differs                        → "changed" (always wins)
- target_kind / target_value / pl_bucket differ → "changed"
- otherwise                                     → None
"""

from __future__ import annotations

from net_alpha.portfolio.plan_diff import (
    PL_DOLLAR_STEP,
    PL_PCT_STEP,
    PlanDiffRow,
    SnapshotRow,
    compute_pl_bucket,
    diff_plan,
)


def _row(
    ticker: str,
    *,
    target_kind: str = "shares",
    target_value: float = 100.0,
    risk_pill: str = "green",
    unrealized_pl: float = 0.0,
    basis: float = 1000.0,
) -> PlanDiffRow:
    return PlanDiffRow(
        ticker=ticker,
        target_kind=target_kind,
        target_value=target_value,
        risk_pill=risk_pill,
        pl_bucket=compute_pl_bucket(unrealized_pl, basis),
    )


def _snap(
    ticker: str,
    *,
    target_kind: str = "shares",
    target_value: float = 100.0,
    risk_pill: str = "green",
    pl_bucket: int = 0,
) -> SnapshotRow:
    return SnapshotRow(
        ticker=ticker,
        target_kind=target_kind,
        target_value=target_value,
        risk_pill=risk_pill,
        pl_bucket=pl_bucket,
    )


def test_added_ticker_is_new():
    current = [_row("NVDA")]
    snapshot = {}
    assert diff_plan(current, snapshot) == {"NVDA": "new"}


def test_unchanged_ticker_is_none():
    current = [_row("AAPL")]
    snapshot = {"AAPL": _snap("AAPL")}
    assert diff_plan(current, snapshot) == {"AAPL": None}


def test_risk_pill_flip_is_changed_even_when_pl_bucket_equal():
    current = [_row("MSFT", risk_pill="yellow")]
    snapshot = {"MSFT": _snap("MSFT", risk_pill="green")}
    assert diff_plan(current, snapshot) == {"MSFT": "changed"}


def test_target_value_change_is_changed():
    current = [_row("TSLA", target_value=200.0)]
    snapshot = {"TSLA": _snap("TSLA", target_value=100.0)}
    assert diff_plan(current, snapshot) == {"TSLA": "changed"}


def test_target_kind_change_is_changed():
    current = [_row("AMD", target_kind="usd")]
    snapshot = {"AMD": _snap("AMD", target_kind="shares")}
    assert diff_plan(current, snapshot) == {"AMD": "changed"}


def test_pl_jitter_within_bucket_is_no_change():
    """Basis $1,000, step = max($250, $50) = $250. $200 → $249 stays in bucket 0."""
    current = [_row("META", unrealized_pl=249.0, basis=1000.0)]
    snapshot = {"META": _snap("META", pl_bucket=0)}
    assert diff_plan(current, snapshot) == {"META": None}


def test_pl_crosses_bucket_is_changed():
    """Basis $1,000, step $250. $200 → $500 crosses to bucket 2."""
    current = [_row("GOOG", unrealized_pl=500.0, basis=1000.0)]
    snapshot = {"GOOG": _snap("GOOG", pl_bucket=0)}
    assert diff_plan(current, snapshot) == {"GOOG": "changed"}


def test_high_basis_uses_pct_step():
    """Basis $50,000 → step = max($250, $2,500) = $2,500. $300 vs $500 stays in bucket 0."""
    current = [_row("BRK.B", unrealized_pl=500.0, basis=50_000.0)]
    snapshot = {"BRK.B": _snap("BRK.B", pl_bucket=0)}
    assert diff_plan(current, snapshot) == {"BRK.B": None}


def test_ticker_only_in_snapshot_is_dropped():
    """Tickers in the snapshot but absent from current rows are not surfaced —
    the row isn't there to badge."""
    current = []
    snapshot = {"OLD": _snap("OLD")}
    assert diff_plan(current, snapshot) == {}


def test_constants_match_spec():
    assert PL_DOLLAR_STEP == 250
    assert PL_PCT_STEP == 0.05
