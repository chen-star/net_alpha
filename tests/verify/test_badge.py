from dataclasses import dataclass

from net_alpha.verify.badge import BadgeStatus, run_inline
from net_alpha.verify.tolerances import Severity


@dataclass
class _Lot:
    id: int
    qty: float
    current_price: float
    market_value: float
    adjusted_basis: float
    unrealized_pl: float
    tacked_acquired_date: str
    bucket: str


@dataclass
class _OverviewSnapshot:
    total_market_value: float
    total_basis: float
    unrealized_pl: float
    realized_pl_ytd: float
    closed_lots_ytd: list
    allocation_rows: list
    leaderboard_rows: list
    lots: list


def _good_snapshot():
    lots = [
        _Lot(1, 100, 150.0, 15000.0, 12000.0, 3000.0, "2025-01-01", "LT"),
        _Lot(2, 50, 100.0, 5000.0, 4000.0, 1000.0, "2025-12-01", "ST"),
    ]
    return _OverviewSnapshot(
        total_market_value=20000.0,
        total_basis=16000.0,
        unrealized_pl=4000.0,
        realized_pl_ytd=0.0,
        closed_lots_ytd=[],
        allocation_rows=[("AAPL", 75.0), ("MSFT", 25.0)],
        leaderboard_rows=[("AAPL", 15000.0), ("MSFT", 5000.0)],
        lots=lots,
    )


def test_run_inline_overview_passes_on_clean_snapshot():
    status = run_inline(snapshot=_good_snapshot(), page="overview")
    assert status.severity == Severity.OK
    assert status.failed == []
    # The dataclass field declaration must be present at runtime.
    assert isinstance(status, BadgeStatus)
    assert status.total() >= 5  # OV-1, OV-2, OV-3, AL-1, AL-2
    assert status.passed_count == status.total()


def test_run_inline_overview_fails_when_kpi_drifts():
    snap = _good_snapshot()
    snap.total_market_value = 25000.0  # drift of $5000
    status = run_inline(snapshot=snap, page="overview")
    assert status.severity == Severity.FAIL
    rule_ids = {f.rule_id for f in status.failed}
    assert "OV-1" in rule_ids
