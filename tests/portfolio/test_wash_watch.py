from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

from net_alpha.models.domain import Trade
from net_alpha.portfolio.wash_watch import recent_loss_closes


def _sell(*, ticker: str, account: str, on: date, proceeds: float, basis: float) -> Trade:
    """Build a sell Trade for tests. Realized P/L = proceeds - basis."""
    return Trade(
        account=account,
        date=on,
        ticker=ticker,
        action="Sell",
        quantity=1,
        proceeds=proceeds,
        cost_basis=basis,
    )


def _repo(trades: list[Trade]) -> MagicMock:
    repo = MagicMock()
    repo.all_trades.return_value = trades
    return repo


def test_no_loss_closes_yields_empty():
    today = date(2026, 4, 26)
    repo = _repo([_sell(ticker="AAPL", account="A", on=date(2026, 4, 1), proceeds=200, basis=100)])  # gain
    rows = recent_loss_closes(repo=repo, today=today, window_days=30)
    assert rows == []


def test_single_loss_in_window_returns_one_row():
    today = date(2026, 4, 26)
    repo = _repo(
        [
            _sell(ticker="TSLA", account="Schwab", on=date(2026, 4, 18), proceeds=100, basis=712),
        ]
    )
    rows = recent_loss_closes(repo=repo, today=today, window_days=30)
    assert len(rows) == 1
    r = rows[0]
    assert r.symbol == "TSLA"
    assert r.account == "Schwab"
    assert r.close_date == date(2026, 4, 18)
    assert r.days_since == 8
    assert r.days_to_safe == 22
    assert r.loss_amount == Decimal("612")


def test_loss_outside_window_excluded():
    today = date(2026, 4, 26)
    repo = _repo(
        [
            _sell(ticker="OLD", account="A", on=date(2026, 3, 26), proceeds=0, basis=100),  # exactly 31d ago
            _sell(ticker="OK", account="A", on=date(2026, 3, 27), proceeds=0, basis=50),  # 30d ago, in window
        ]
    )
    rows = recent_loss_closes(repo=repo, today=today, window_days=30)
    syms = [r.symbol for r in rows]
    assert "OLD" not in syms
    assert "OK" in syms


def test_multiple_losses_same_symbol_collapsed_to_most_recent_summed_loss():
    today = date(2026, 4, 26)
    repo = _repo(
        [
            _sell(ticker="META", account="Schwab", on=date(2026, 4, 5), proceeds=100, basis=200),  # -100
            _sell(ticker="META", account="Fidelity", on=date(2026, 4, 11), proceeds=80, basis=260),  # -180
        ]
    )
    rows = recent_loss_closes(repo=repo, today=today, window_days=30)
    assert len(rows) == 1
    r = rows[0]
    assert r.symbol == "META"
    assert r.account == "Fidelity"  # account from the most recent close
    assert r.close_date == date(2026, 4, 11)
    assert r.loss_amount == Decimal("280")  # 100 + 180


def test_account_filter():
    today = date(2026, 4, 26)
    repo = _repo(
        [
            _sell(ticker="X", account="Schwab", on=date(2026, 4, 10), proceeds=0, basis=50),
            _sell(ticker="Y", account="Fidelity", on=date(2026, 4, 10), proceeds=0, basis=80),
        ]
    )
    rows = recent_loss_closes(repo=repo, today=today, window_days=30, account="Schwab")
    assert [r.symbol for r in rows] == ["X"]


def test_sorted_by_close_date_desc():
    today = date(2026, 4, 26)
    repo = _repo(
        [
            _sell(ticker="A", account="X", on=date(2026, 4, 2), proceeds=0, basis=10),
            _sell(ticker="B", account="X", on=date(2026, 4, 20), proceeds=0, basis=10),
            _sell(ticker="C", account="X", on=date(2026, 4, 11), proceeds=0, basis=10),
        ]
    )
    rows = recent_loss_closes(repo=repo, today=today, window_days=30)
    assert [r.symbol for r in rows] == ["B", "C", "A"]


def test_days_to_safe_clamped_at_zero():
    today = date(2026, 4, 26)
    repo = _repo(
        [
            _sell(ticker="EDGE", account="X", on=date(2026, 3, 27), proceeds=0, basis=100),  # 30d ago
        ]
    )
    rows = recent_loss_closes(repo=repo, today=today, window_days=30)
    assert len(rows) == 1
    assert rows[0].days_to_safe == 0
