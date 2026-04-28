from datetime import date, timedelta
from decimal import Decimal

from net_alpha.engine.lockout import compute_lockout_clear_date
from net_alpha.models.domain import OptionDetails, Trade
from net_alpha.portfolio.tax_planner import (
    CSPAssigned,
    extract_premium_origin,
)


def test_extract_premium_origin_for_csp_assigned_buy() -> None:
    """A Buy trade with basis_source 'option_short_open_assigned' is CSP-originated.

    Schwab parser emits this synthetic Buy when a sold put is assigned. We must
    pair it back to the originating STO leg to recover premium received.
    """
    sto = Trade(
        account="Schwab Tax",
        date=date(2025, 8, 14),
        ticker="UUUU",
        action="Sell to Open",
        quantity=Decimal("1"),
        proceeds=Decimal("120"),
        cost_basis=Decimal("0"),
        option_details=OptionDetails(strike=Decimal("5"), expiry=date(2025, 9, 19), call_put="P"),
        basis_source="option_short_open",
    )
    btc_assigned = Trade(
        account="Schwab Tax",
        date=date(2025, 9, 19),
        ticker="UUUU",
        action="Buy to Close",
        quantity=Decimal("1"),
        proceeds=Decimal("0"),
        cost_basis=Decimal("0"),
        option_details=OptionDetails(strike=Decimal("5"), expiry=date(2025, 9, 19), call_put="P"),
        basis_source="option_short_close_assigned",
    )
    assigned_buy = Trade(
        account="Schwab Tax",
        date=date(2025, 9, 19),
        ticker="UUUU",
        action="Buy",
        quantity=Decimal("100"),
        proceeds=Decimal("0"),
        cost_basis=Decimal("380"),  # 5*100 - 120 = 380 (basis already premium-reduced)
        basis_source="option_short_open_assigned",
    )

    origin = extract_premium_origin(
        lot_trade=assigned_buy,
        all_trades=[sto, btc_assigned, assigned_buy],
    )
    assert isinstance(origin, CSPAssigned)
    assert origin.premium_received == Decimal("120")
    assert origin.strike == Decimal("5")
    assert origin.option_natural_key == "UUUU 09/19/2025 5.00 P"


def test_extract_premium_origin_returns_none_for_normal_buy() -> None:
    normal_buy = Trade(
        account="Schwab Tax",
        date=date(2025, 1, 1),
        ticker="AAPL",
        action="Buy",
        quantity=Decimal("100"),
        proceeds=Decimal("0"),
        cost_basis=Decimal("15000"),
        basis_source="unknown",
    )
    assert extract_premium_origin(normal_buy, []) is None


def test_close_stock_at_loss_locks_out_new_csp_open(
    repo,
    schwab_account,
    seed_import,
) -> None:
    """
    Spec section 2e: closing assigned shares at a loss should lock out new CSP
    opens on the same underlying for 30 days.

    The lockout function answers symmetrically: an open CSP on UUUU extends
    UUUU's lockout-clear date because closing the underlying at a loss while
    a CSP is open is a wash sale.
    """
    today = date(2026, 5, 1)
    stock_buy = Trade(
        account=schwab_account.display(),
        date=today - timedelta(days=60),
        ticker="UUUU",
        action="Buy",
        quantity=Decimal("100"),
        proceeds=Decimal("0"),
        cost_basis=Decimal("1000"),
    )
    stock_sell_at_loss = Trade(
        account=schwab_account.display(),
        date=today - timedelta(days=10),
        ticker="UUUU",
        action="Sell",
        quantity=Decimal("100"),
        proceeds=Decimal("400"),
        cost_basis=Decimal("1000"),
    )
    seed_import(repo, schwab_account, [stock_buy, stock_sell_at_loss])
    proposed_csp = Trade(
        account=schwab_account.display(),
        date=today,
        ticker="UUUU",
        action="Sell to Open",
        quantity=Decimal("1"),
        proceeds=Decimal("60"),
        cost_basis=Decimal("0"),
        option_details=OptionDetails(
            strike=Decimal("5"),
            expiry=today + timedelta(days=30),
            call_put="P",
        ),
        basis_source="option_short_open",
    )
    all_trades = [stock_buy, stock_sell_at_loss, proposed_csp]
    clear = compute_lockout_clear_date(
        symbol="UUUU",
        account=schwab_account.display(),
        all_trades=all_trades,
        as_of=today,
        etf_pairs={},
    )
    assert clear is not None
    assert clear == today + timedelta(days=31)


def test_csp_origin_round_trip_through_repo(
    repo,
    schwab_account,
    seed_import,
) -> None:
    """End-to-end: CSP chain seeded into repo, premium origin still recoverable."""
    sto = Trade(
        account=schwab_account.display(),
        date=date(2025, 8, 14),
        ticker="UUUU",
        action="Sell to Open",
        quantity=Decimal("1"),
        proceeds=Decimal("120"),
        cost_basis=Decimal("0"),
        option_details=OptionDetails(
            strike=Decimal("5"),
            expiry=date(2025, 9, 19),
            call_put="P",
        ),
        basis_source="option_short_open",
    )
    btc = Trade(
        account=schwab_account.display(),
        date=date(2025, 9, 19),
        ticker="UUUU",
        action="Buy to Close",
        quantity=Decimal("1"),
        proceeds=Decimal("0"),
        cost_basis=Decimal("0"),
        option_details=OptionDetails(
            strike=Decimal("5"),
            expiry=date(2025, 9, 19),
            call_put="P",
        ),
        basis_source="option_short_close_assigned",
    )
    assigned = Trade(
        account=schwab_account.display(),
        date=date(2025, 9, 19),
        ticker="UUUU",
        action="Buy",
        quantity=Decimal("100"),
        proceeds=Decimal("0"),
        cost_basis=Decimal("380"),
        basis_source="option_short_open_assigned",
    )
    seed_import(repo, schwab_account, [sto, btc, assigned])

    all_t = repo.all_trades()
    assigned_buys = [t for t in all_t if t.basis_source == "option_short_open_assigned"]
    assert len(assigned_buys) == 1

    origin = extract_premium_origin(assigned_buys[0], all_t)
    assert origin is not None
    assert origin.premium_received == Decimal("120")
