from dataclasses import dataclass

from net_alpha.verify.invariants import (
    InvariantResult,
    check_ov1_total_market_value,
    check_ov2_unrealized_consistency,
    check_ov3_realized_ytd,
)
from net_alpha.verify.tolerances import Severity, Tolerance


@dataclass
class _Lot:
    market_value: float
    adjusted_basis: float
    unrealized_pl: float


def test_ov1_passes_when_total_matches_sum_of_lots():
    lots = [_Lot(100.0, 80.0, 20.0), _Lot(50.0, 40.0, 10.0)]
    result = check_ov1_total_market_value(
        total_market_value=150.0,
        lots=lots,
        tol=Tolerance(abs=0.01, rel=0.0001),
    )
    assert result.severity == Severity.OK
    assert result.rule_id == "OV-1"


def test_ov1_warns_at_small_drift():
    lots = [_Lot(100.0, 80.0, 20.0), _Lot(50.0, 40.0, 10.0)]
    result = check_ov1_total_market_value(
        total_market_value=150.05,  # delta=0.05, within 10x0.01
        lots=lots,
        tol=Tolerance(abs=0.01, rel=0.0001),
    )
    assert result.severity == Severity.WARN
    assert result.ours == 150.05
    assert result.theirs == 150.0
    assert abs(result.delta - 0.05) < 1e-9


def test_ov1_fails_at_large_drift():
    lots = [_Lot(100.0, 80.0, 20.0), _Lot(50.0, 40.0, 10.0)]
    result = check_ov1_total_market_value(
        total_market_value=200.0,
        lots=lots,
        tol=Tolerance(abs=0.01, rel=0.0001),
    )
    assert result.severity == Severity.FAIL


def test_ov2_passes_when_unrealized_matches_mv_minus_basis():
    result = check_ov2_unrealized_consistency(
        total_market_value=1500.0,
        total_basis=1200.0,
        unrealized_pl=300.0,
        tol=Tolerance(abs=0.01, rel=0.0001),
    )
    assert result.severity == Severity.OK


def test_ov2_fails_when_drift_large():
    result = check_ov2_unrealized_consistency(
        total_market_value=1500.0,
        total_basis=1200.0,
        unrealized_pl=350.0,  # should be 300
        tol=Tolerance(abs=0.01, rel=0.0001),
    )
    assert result.severity == Severity.FAIL


def test_ov3_passes_when_ytd_matches_sum_of_closed_lots():
    closed = [_Lot(0.0, 100.0, -20.0), _Lot(0.0, 50.0, 30.0)]  # unrealized_pl repurposed as realized_pl here
    result = check_ov3_realized_ytd(
        realized_pl_ytd=10.0,
        closed_lots_ytd=[(lot.unrealized_pl,) for lot in closed],
        tol=Tolerance(abs=0.01, rel=0.0001),
    )
    assert result.severity == Severity.OK


def test_invariant_result_serializes_to_dict():
    lots = [_Lot(100.0, 80.0, 20.0)]
    result = check_ov1_total_market_value(
        total_market_value=100.0,
        lots=lots,
        tol=Tolerance(abs=0.01, rel=0.0001),
    )
    d = result.to_dict()
    assert d["rule_id"] == "OV-1"
    assert d["severity"] == "ok"
    # Touch the import so ruff doesn't trim it.
    assert InvariantResult is not None


# --- Task 6: Allocation invariants (AL-1, AL-2) -----------------------------

from net_alpha.verify.invariants import (  # noqa: E402
    check_al1_allocation_sums_to_100,
    check_al2_leaderboard_weight,
)


def test_al1_passes_when_pct_sums_to_100():
    rows = [("AAPL", 40.0), ("MSFT", 35.0), ("GOOG", 25.0)]
    result = check_al1_allocation_sums_to_100(
        allocation_rows=rows,
        tol=Tolerance(abs=0.01, rel=0.0001),
    )
    assert result.severity == Severity.OK


def test_al1_fails_when_pct_off():
    rows = [("AAPL", 40.0), ("MSFT", 35.0), ("GOOG", 30.0)]  # sums to 105
    result = check_al1_allocation_sums_to_100(
        allocation_rows=rows,
        tol=Tolerance(abs=0.01, rel=0.0001),
    )
    assert result.severity == Severity.FAIL


def test_al2_passes_when_leaderboard_weight_matches_total_mv():
    rows = [("AAPL", 1000.0), ("MSFT", 500.0)]
    result = check_al2_leaderboard_weight(
        leaderboard_rows=rows,
        total_market_value=1500.0,
        tol=Tolerance(abs=0.01, rel=0.0001),
    )
    assert result.severity == Severity.OK


def test_al2_fails_when_leaderboard_drifts():
    rows = [("AAPL", 1000.0), ("MSFT", 500.0)]
    result = check_al2_leaderboard_weight(
        leaderboard_rows=rows,
        total_market_value=1600.0,  # drift of $100
        tol=Tolerance(abs=0.01, rel=0.0001),
    )
    assert result.severity == Severity.FAIL


# --- Task 7: Per-lot invariants (PL-1, PL-2, PL-3) --------------------------

from datetime import date  # noqa: E402

from net_alpha.verify.invariants import (  # noqa: E402
    check_pl1_value_consistency,
    check_pl2_pnl_consistency,
    check_pl3_holding_period,
)


def test_pl1_passes_when_qty_times_price_matches_mv():
    results = check_pl1_value_consistency(
        lot_rows=[
            {"id": 1, "qty": 100, "current_price": 150.0, "market_value": 15000.0},
            {"id": 2, "qty": 50, "current_price": 100.0, "market_value": 5000.0},
        ],
        tol=Tolerance(abs=0.01, rel=0.0001),
    )
    assert all(r.severity == Severity.OK for r in results)
    assert {r.rule_id for r in results} == {"PL-1"}


def test_pl1_fails_for_drifted_lot():
    results = check_pl1_value_consistency(
        lot_rows=[
            {"id": 1, "qty": 100, "current_price": 150.0, "market_value": 14000.0},  # drift $1000
        ],
        tol=Tolerance(abs=0.01, rel=0.0001),
    )
    assert results[0].severity == Severity.FAIL
    assert results[0].scope == "lot:1"


def test_pl2_passes_when_pnl_matches_mv_minus_basis():
    results = check_pl2_pnl_consistency(
        lot_rows=[
            {"id": 1, "market_value": 15000.0, "adjusted_basis": 12000.0, "unrealized_pl": 3000.0},
        ],
        tol=Tolerance(abs=0.01, rel=0.0001),
    )
    assert results[0].severity == Severity.OK


def test_pl2_fails_when_pnl_off():
    results = check_pl2_pnl_consistency(
        lot_rows=[
            {"id": 1, "market_value": 15000.0, "adjusted_basis": 12000.0, "unrealized_pl": 4000.0},
        ],
        tol=Tolerance(abs=0.01, rel=0.0001),
    )
    assert results[0].severity == Severity.FAIL


def test_pl3_long_term_with_tacking():
    # Lot acquired 400 days ago via wash-sale tacking -> LT bucket required.
    today = date(2026, 5, 11)
    results = check_pl3_holding_period(
        lot_rows=[
            {"id": 1, "tacked_acquired_date": "2025-04-06", "bucket": "LT"},  # 400 days ago
        ],
        today=today,
    )
    assert results[0].severity == Severity.OK


def test_pl3_fails_when_bucket_wrong():
    today = date(2026, 5, 11)
    results = check_pl3_holding_period(
        lot_rows=[
            {"id": 1, "tacked_acquired_date": "2026-04-01", "bucket": "LT"},  # 40 days, must be ST
        ],
        today=today,
    )
    assert results[0].severity == Severity.FAIL
    assert "expected ST" in results[0].detail.get("reason", "")


# --- Task 8: Cross-page cache + XP-1 ----------------------------------------

from net_alpha.verify.badge import (  # noqa: E402
    OverviewTotalCache,
    read_overview_total,
    snapshot_overview_total,
)
from net_alpha.verify.invariants import check_xp1_cross_page  # noqa: E402


def test_overview_total_cache_round_trip():
    cache = OverviewTotalCache()
    snapshot_overview_total(cache, total_market_value=12345.67)
    cached = read_overview_total(cache, max_age_seconds=60)
    assert cached == 12345.67


def test_overview_total_cache_returns_none_when_empty():
    cache = OverviewTotalCache()
    assert read_overview_total(cache, max_age_seconds=60) is None


def test_overview_total_cache_returns_none_when_stale():
    cache = OverviewTotalCache()
    snapshot_overview_total(cache, total_market_value=100.0, _now=lambda: 1000.0)
    cached = read_overview_total(cache, max_age_seconds=60, _now=lambda: 1100.0)  # 100s later
    assert cached is None


def test_xp1_skips_when_no_cached_overview_total():
    result = check_xp1_cross_page(
        positions_sum=12345.67,
        cached_overview_total=None,
        tol=Tolerance(abs=0.01, rel=0.0001),
    )
    assert result.severity == Severity.OK  # not_checked is OK from the badge's perspective
    assert result.detail.get("skipped") is True


def test_xp1_fails_when_pages_disagree():
    result = check_xp1_cross_page(
        positions_sum=10000.0,
        cached_overview_total=9000.0,
        tol=Tolerance(abs=0.01, rel=0.0001),
    )
    assert result.severity == Severity.FAIL
