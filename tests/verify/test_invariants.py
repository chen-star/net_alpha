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
