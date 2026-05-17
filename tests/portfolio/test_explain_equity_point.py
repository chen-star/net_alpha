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


from net_alpha.models.domain import Trade
from net_alpha.portfolio.explain import build_equity_point_breakdown


def _make_sell_trade(*, on: date, ticker: str, qty: Decimal, proceeds: Decimal, basis: Decimal) -> Trade:
    return Trade(
        id="t1",
        account="Brokerage",
        date=on,
        ticker=ticker,
        action="Sell",
        quantity=float(qty),
        proceeds=float(proceeds),
        cost_basis=float(basis),
    )


def test_trade_only_day_attributes_realized_to_realized_pnl():
    on = date(2026, 5, 10)
    prev = date(2026, 5, 9)
    trade = _make_sell_trade(on=on, ticker="AAPL", qty=Decimal("100"), proceeds=Decimal("18200"), basis=Decimal("17000"))

    b = build_equity_point_breakdown(
        on=on,
        previous_on=prev,
        trades_on_date=[trade],
        cash_events_on_date=[],
        dividend_events_on_date=[],
        open_lots_prev_day=[],
        violations_on_date=[],
        exempt_matches_on_date=[],
        get_close=lambda sym, d: None,
        delta_account_value=Decimal("1200"),
    )
    assert b.realized_pnl == Decimal("1200.00")
    assert b.contributions == Decimal("0")
    assert b.delta_unrealized == Decimal("0")
    assert b.dividends == Decimal("0")
    assert len(b.trades) == 1
    assert b.trades[0].ticker == "AAPL"
    assert b.trades[0].realized_pnl == Decimal("1200.00")
    assert b.residual == Decimal("0")
    assert b.is_starting_snapshot is False
