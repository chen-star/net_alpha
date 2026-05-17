from datetime import date
from decimal import Decimal

from net_alpha.portfolio.explain import (
    CashEventRow,
    DividendRow,
    EquityPointBreakdown,
    MoverRow,
    TradeRow,
    WashEventRef,
)


def test_breakdown_dataclass_constructs_with_all_fields():
    b = EquityPointBreakdown(
        on=date(2026, 5, 10),
        previous_on=date(2026, 5, 9),
        delta_account_value=Decimal("123.45"),
        contributions=Decimal("0"),
        realized_pnl=Decimal("23.45"),
        delta_unrealized=Decimal("100.00"),
        dividends=Decimal("0"),
        residual=Decimal("0"),
        trades=[],
        top_movers=[],
        cash_events=[],
        dividend_events=[],
        wash_events=[],
        unpriced_tickers=(),
        unpriced_basis_total=Decimal("0"),
        is_starting_snapshot=False,
        starting_holdings_count=0,
        starting_contributed_to_date=Decimal("0"),
    )
    assert b.on == date(2026, 5, 10)
    assert b.previous_on == date(2026, 5, 9)
    assert b.is_starting_snapshot is False


def test_row_dataclasses_construct():
    TradeRow(
        trade_id="42",
        ticker="AAPL",
        side="Sell",
        quantity=Decimal("100"),
        realized_pnl=Decimal("250.00"),
    )
    MoverRow(
        ticker="SPY",
        shares=Decimal("50"),
        prev_close=Decimal("500"),
        close=Decimal("502"),
        contribution=Decimal("100"),
    )
    CashEventRow(
        account="Schwab Brokerage",
        kind="transfer_in",
        amount=Decimal("1000"),
    )
    DividendRow(
        ticker="MSFT",
        amount=Decimal("12.34"),
    )
    WashEventRef(
        kind="violation",
        row_id=7,
        ticker="QQQ",
    )
