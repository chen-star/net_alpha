from datetime import date
from decimal import Decimal

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
