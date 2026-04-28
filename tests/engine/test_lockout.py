from datetime import date
from decimal import Decimal

from net_alpha.engine.lockout import compute_lockout_clear_date
from net_alpha.models.domain import Trade


def _buy(account: str, ticker: str, on: date, qty: int = 10) -> Trade:
    return Trade(
        account=account,
        date=on,
        ticker=ticker,
        action="Buy",
        quantity=Decimal(qty),
        proceeds=Decimal("0"),
        cost_basis=Decimal(qty * 10),
    )


def test_no_recent_buys_returns_none() -> None:
    assert (
        compute_lockout_clear_date(
            symbol="AAPL",
            account="Schwab Tax",
            all_trades=[],
            as_of=date(2026, 5, 1),
            etf_pairs={},
        )
        is None
    )


def test_recent_buy_extends_lockout_30_days() -> None:
    buy = _buy("Schwab Tax", "AAPL", date(2026, 4, 15))
    clear = compute_lockout_clear_date(
        symbol="AAPL",
        account="Schwab Tax",
        all_trades=[buy],
        as_of=date(2026, 5, 1),
        etf_pairs={},
    )
    # 31 days after the most recent buy (day 0 is buy date; sale on day 31 is safe).
    assert clear == date(2026, 5, 16)


def test_buy_in_substantially_identical_pair_extends_lockout() -> None:
    buy = _buy("Schwab Tax", "VOO", date(2026, 4, 15))
    clear = compute_lockout_clear_date(
        symbol="SPY",
        account="Schwab Tax",
        all_trades=[buy],
        as_of=date(2026, 5, 1),
        etf_pairs={"S&P 500": ["SPY", "VOO", "IVV", "SPLG"]},
    )
    assert clear == date(2026, 5, 16)


def test_cross_account_buy_also_locks_out() -> None:
    buy = _buy("Fidelity Tax", "AAPL", date(2026, 4, 15))
    clear = compute_lockout_clear_date(
        symbol="AAPL",
        account="Schwab Tax",
        all_trades=[buy],
        as_of=date(2026, 5, 1),
        etf_pairs={},
    )
    # Wash-sale rules apply across accounts of the same taxpayer.
    assert clear == date(2026, 5, 16)


def test_old_buy_ignored() -> None:
    buy = _buy("Schwab Tax", "AAPL", date(2026, 1, 1))
    clear = compute_lockout_clear_date(
        symbol="AAPL",
        account="Schwab Tax",
        all_trades=[buy],
        as_of=date(2026, 5, 1),
        etf_pairs={},
    )
    assert clear is None
