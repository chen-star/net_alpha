from datetime import date
from decimal import Decimal

from net_alpha.portfolio.models import AccountValuePoint


def test_account_value_point_constructs_with_all_fields():
    p = AccountValuePoint(
        on=date(2025, 8, 14),
        contributions=Decimal("200000"),
        holdings_value=Decimal("180000"),
        cash_balance=Decimal("87432"),
        account_value=Decimal("267432"),
        net_pl=Decimal("67432"),
    )
    assert p.on == date(2025, 8, 14)
    assert p.account_value == Decimal("267432")
    assert p.net_pl == Decimal("67432")


def test_account_value_point_allows_none_for_unpriced_dates():
    p = AccountValuePoint(
        on=date(2025, 8, 14),
        contributions=Decimal("200000"),
        holdings_value=None,
        cash_balance=Decimal("87432"),
        account_value=None,
        net_pl=None,
    )
    assert p.holdings_value is None
    assert p.account_value is None
    assert p.net_pl is None
