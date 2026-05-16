"""Tests for BasisRecon detail annotations (§1256 + cross-account)."""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import MagicMock

from net_alpha.verify.broker_recon import (
    _expected_cross_account,  # noqa: F401 — staged for Task 4 cross-account tests
    _expected_section_1256,
    reconcile_open_positions,
)
from net_alpha.verify.tolerances import Severity, load_tolerances

# --- §1256 helper ---------------------------------------------------------


def test_expected_section_1256_true_when_underlying_crosses_year_end():
    """SPX opened 2025-12-15, snapshot 2026-05-16 → expected True."""
    assert (
        _expected_section_1256(
            symbol="SPX",
            earliest_open_date=date(2025, 12, 15),
            snapshot_date=date(2026, 5, 16),
            universe={"SPX", "NDX", "RUT"},
        )
        is True
    )


def test_expected_section_1256_false_same_year():
    """SPX opened 2026-01-10, snapshot 2026-05-16 → no year-end crossed."""
    assert (
        _expected_section_1256(
            symbol="SPX",
            earliest_open_date=date(2026, 1, 10),
            snapshot_date=date(2026, 5, 16),
            universe={"SPX"},
        )
        is False
    )


def test_expected_section_1256_false_non_universe():
    """AAPL is not §1256."""
    assert (
        _expected_section_1256(
            symbol="AAPL",
            earliest_open_date=date(2024, 1, 1),
            snapshot_date=date(2026, 5, 16),
            universe={"SPX"},
        )
        is False
    )


def test_expected_section_1256_false_when_no_open_date():
    """No open date → cannot prove year-end was crossed → False."""
    assert (
        _expected_section_1256(
            symbol="SPX",
            earliest_open_date=None,
            snapshot_date=date(2026, 5, 16),
            universe={"SPX"},
        )
        is False
    )


# --- reconcile_open_positions integration ---------------------------------


def _stub_repo(
    *,
    broker_rows: list[Any],
    our_rows: list[dict],
    lots: list[Any] | None = None,
    violations: list[Any] | None = None,
    trades: list[Any] | None = None,
    as_of: str | None = "2026-05-16",
):
    """Minimal repo stub for reconcile_open_positions."""
    repo = MagicMock()
    repo.latest_broker_positions.return_value = (broker_rows, as_of)
    repo.aggregate_open_positions.return_value = our_rows
    repo.all_lots.return_value = lots or []
    repo.get_violations_for_ticker.return_value = violations or []
    repo.all_trades.return_value = trades or []
    return repo


def _bp(account_label: str, symbol: str, qty: float, cost_basis: float, market_value: float):
    """Build a BrokerPosition-like object."""
    bp = MagicMock()
    bp.account_label = account_label
    bp.symbol = symbol
    bp.qty = qty
    bp.cost_basis = cost_basis
    bp.market_value = market_value
    return bp


def _lot(account: str, ticker: str, acquired_date: date):
    lot = MagicMock()
    lot.account = account
    lot.ticker = ticker
    lot.option_details = None
    lot.date = acquired_date
    return lot


def test_basis_recon_flags_section_1256_year_end_divergence():
    """SPX position opened last year, basis disagrees → expected_section_1256=True."""
    tol = load_tolerances()
    repo = _stub_repo(
        broker_rows=[_bp("A", "SPX", 1.0, 5000.0, 5200.0)],
        our_rows=[
            {
                "account_label": "A",
                "symbol": "SPX",
                "qty": 1.0,
                "adjusted_basis_total": 4500.0,  # $500 divergence — Schwab MTM'd
                "market_value_total": 5200.0,
            }
        ],
        lots=[_lot("A", "SPX", date(2025, 12, 15))],
        as_of="2026-05-16",
    )
    findings, _ = reconcile_open_positions(repo=repo, tol_cfg=tol, today=date(2026, 5, 16))
    basis = [f for f in findings if f.rule_id == "BasisRecon"]
    assert len(basis) == 1
    assert basis[0].detail.get("expected_section_1256") is True


def test_basis_recon_no_flag_for_non_1256_symbol():
    """AAPL basis diff → no annotation."""
    tol = load_tolerances()
    repo = _stub_repo(
        broker_rows=[_bp("A", "AAPL", 100.0, 15000.0, 18000.0)],
        our_rows=[
            {
                "account_label": "A",
                "symbol": "AAPL",
                "qty": 100.0,
                "adjusted_basis_total": 14500.0,
                "market_value_total": 18000.0,
            }
        ],
        lots=[_lot("A", "AAPL", date(2024, 1, 1))],
        as_of="2026-05-16",
    )
    findings, _ = reconcile_open_positions(repo=repo, tol_cfg=tol, today=date(2026, 5, 16))
    basis = [f for f in findings if f.rule_id == "BasisRecon"]
    assert len(basis) == 1
    assert basis[0].detail.get("expected_section_1256") is not True


def test_basis_recon_severity_unchanged_by_annotation():
    """Annotation must not lower severity — it's informational only."""
    tol = load_tolerances()
    repo = _stub_repo(
        broker_rows=[_bp("A", "SPX", 1.0, 5000.0, 5200.0)],
        our_rows=[
            {
                "account_label": "A",
                "symbol": "SPX",
                "qty": 1.0,
                "adjusted_basis_total": 4500.0,
                "market_value_total": 5200.0,
            }
        ],
        lots=[_lot("A", "SPX", date(2025, 12, 15))],
        as_of="2026-05-16",
    )
    findings, _ = reconcile_open_positions(repo=repo, tol_cfg=tol, today=date(2026, 5, 16))
    basis = [f for f in findings if f.rule_id == "BasisRecon"]
    assert basis[0].severity != Severity.OK  # still classified as a finding


# --- cross-account helper -------------------------------------------------


def _trade(trade_id: str, account: str, ticker: str):
    t = MagicMock()
    t.id = trade_id
    t.account = account
    t.ticker = ticker
    return t


def _violation(loss_trade_id: str, buy_trade_id: str):
    v = MagicMock()
    v.loss_trade_id = loss_trade_id
    v.buy_trade_id = buy_trade_id
    return v


def test_expected_cross_account_true_when_legs_in_different_accounts():
    """Loss in account A, replacement in account B → True for both."""
    trades_by_id = {
        "T1": _trade("T1", "A", "AAPL"),
        "T2": _trade("T2", "B", "AAPL"),
    }
    violations = [_violation(loss_trade_id="T1", buy_trade_id="T2")]
    assert (
        _expected_cross_account(account_label="A", symbol="AAPL", violations=violations, trades_by_id=trades_by_id)
        is True
    )
    assert (
        _expected_cross_account(account_label="B", symbol="AAPL", violations=violations, trades_by_id=trades_by_id)
        is True
    )


def test_expected_cross_account_false_when_same_account():
    """Wash sale fully inside one account → not cross-account."""
    trades_by_id = {
        "T1": _trade("T1", "A", "AAPL"),
        "T2": _trade("T2", "A", "AAPL"),
    }
    violations = [_violation("T1", "T2")]
    assert (
        _expected_cross_account(account_label="A", symbol="AAPL", violations=violations, trades_by_id=trades_by_id)
        is False
    )


def test_expected_cross_account_false_when_account_not_touched():
    """Violation across A and B; querying account C → False."""
    trades_by_id = {
        "T1": _trade("T1", "A", "AAPL"),
        "T2": _trade("T2", "B", "AAPL"),
    }
    violations = [_violation("T1", "T2")]
    assert (
        _expected_cross_account(account_label="C", symbol="AAPL", violations=violations, trades_by_id=trades_by_id)
        is False
    )


def test_expected_cross_account_false_when_no_violations():
    assert _expected_cross_account(account_label="A", symbol="AAPL", violations=[], trades_by_id={}) is False


def test_basis_recon_flags_cross_account_when_violation_crosses():
    """End-to-end: BasisRecon finding gets expected_cross_account=True."""
    tol = load_tolerances()
    trades = [
        _trade("T1", "A", "AAPL"),
        _trade("T2", "B", "AAPL"),
    ]
    violations = [_violation("T1", "T2")]
    repo = _stub_repo(
        broker_rows=[_bp("A", "AAPL", 100.0, 15000.0, 18000.0)],
        our_rows=[
            {
                "account_label": "A",
                "symbol": "AAPL",
                "qty": 100.0,
                "adjusted_basis_total": 14500.0,
                "market_value_total": 18000.0,
            }
        ],
        lots=[_lot("A", "AAPL", date(2024, 1, 1))],
        violations=violations,
        trades=trades,
        as_of="2026-05-16",
    )
    findings, _ = reconcile_open_positions(repo=repo, tol_cfg=tol, today=date(2026, 5, 16))
    basis = [f for f in findings if f.rule_id == "BasisRecon"]
    assert len(basis) == 1
    assert basis[0].detail.get("expected_cross_account") is True


def test_basis_recon_both_flags_when_section_1256_and_cross_account():
    """SPX cross-account wash sale opened last year → both flags True."""
    tol = load_tolerances()
    trades = [
        _trade("T1", "A", "SPX"),
        _trade("T2", "B", "SPX"),
    ]
    violations = [_violation("T1", "T2")]
    repo = _stub_repo(
        broker_rows=[_bp("A", "SPX", 1.0, 5000.0, 5200.0)],
        our_rows=[
            {
                "account_label": "A",
                "symbol": "SPX",
                "qty": 1.0,
                "adjusted_basis_total": 4500.0,
                "market_value_total": 5200.0,
            }
        ],
        lots=[_lot("A", "SPX", date(2025, 12, 15))],
        violations=violations,
        trades=trades,
        as_of="2026-05-16",
    )
    findings, _ = reconcile_open_positions(repo=repo, tol_cfg=tol, today=date(2026, 5, 16))
    basis = [f for f in findings if f.rule_id == "BasisRecon"]
    assert basis[0].detail.get("expected_section_1256") is True
    assert basis[0].detail.get("expected_cross_account") is True
