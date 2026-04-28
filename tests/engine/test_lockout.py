from datetime import date
from decimal import Decimal

from net_alpha.engine.lockout import compute_lockout_clear_date
from net_alpha.models.domain import OptionDetails, Trade


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


def test_open_csp_locks_out_stock_loss_close() -> None:
    """Selling a put (CSP open) creates a wash-sale exposure for the underlying.

    Closing the underlying stock at a loss within 30 days of an open short put on
    the same name is a wash sale. This is the key wheel-strategy pitfall.
    """
    sto = Trade(
        account="Schwab Tax",
        date=date(2026, 4, 15),
        ticker="UUUU",
        action="Sell to Open",
        quantity=Decimal("1"),
        proceeds=Decimal("60"),
        cost_basis=Decimal("0"),
        option_details=OptionDetails(
            strike=Decimal("5"),
            expiry=date(2026, 5, 16),
            call_put="P",
        ),
        basis_source="option_short_open",
    )
    clear = compute_lockout_clear_date(
        symbol="UUUU",
        account="Schwab Tax",
        all_trades=[sto],
        as_of=date(2026, 4, 20),
        etf_pairs={},
    )
    assert clear == date(2026, 5, 16)


def test_long_call_open_does_not_lock_out_underlying() -> None:
    bto = Trade(
        account="Schwab Tax",
        date=date(2026, 4, 15),
        ticker="UUUU",
        action="Buy to Open",
        quantity=Decimal("1"),
        proceeds=Decimal("0"),
        cost_basis=Decimal("60"),
        option_details=OptionDetails(
            strike=Decimal("8"),
            expiry=date(2026, 5, 16),
            call_put="C",
        ),
        basis_source="option_long_open",
    )
    clear = compute_lockout_clear_date(
        symbol="UUUU",
        account="Schwab Tax",
        all_trades=[bto],
        as_of=date(2026, 4, 20),
        etf_pairs={},
    )
    # A long call open is NOT substantially identical to the underlying for §1091
    # purposes (call long is not auto-deemed S/I; we conservatively excluded it).
    assert clear is None
