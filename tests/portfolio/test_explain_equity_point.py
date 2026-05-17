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


from net_alpha.models.domain import CashEvent, Lot, Trade, WashSaleViolation
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


def test_contribution_only_day_attributes_to_contributions():
    on = date(2026, 5, 10)
    ev = CashEvent(
        account="Brokerage",
        event_date=on,
        kind="transfer_in",
        amount=5000.0,
        ticker=None,
        description="ACH transfer",
    )
    b = build_equity_point_breakdown(
        on=on,
        previous_on=date(2026, 5, 9),
        trades_on_date=[],
        cash_events_on_date=[ev],
        dividend_events_on_date=[],
        open_lots_prev_day=[],
        violations_on_date=[],
        exempt_matches_on_date=[],
        get_close=lambda sym, d: None,
        delta_account_value=Decimal("5000"),
    )
    assert b.contributions == Decimal("5000")
    assert len(b.cash_events) == 1
    assert b.cash_events[0].kind == "transfer_in"
    assert b.cash_events[0].amount == Decimal("5000")
    assert b.residual == Decimal("0")


def test_mtm_only_day_attributes_to_delta_unrealized():
    on = date(2026, 5, 10)
    prev = date(2026, 5, 9)
    lots = [
        Lot(
            id="L1",
            trade_id="t-aapl",
            account="Brokerage",
            ticker="AAPL",
            date=date(2026, 1, 5),
            quantity=100.0,
            cost_basis=17000.0,
            adjusted_basis=17000.0,
        ),
        Lot(
            id="L2",
            trade_id="t-spy",
            account="Brokerage",
            ticker="SPY",
            date=date(2026, 1, 6),
            quantity=10.0,
            cost_basis=5000.0,
            adjusted_basis=5000.0,
        ),
    ]
    closes = {
        ("AAPL", prev): Decimal("180.00"),
        ("AAPL", on): Decimal("182.00"),  # +$200 on 100 shares
        ("SPY", prev): Decimal("500.00"),
        ("SPY", on): Decimal("498.00"),  # -$20 on 10 shares
    }

    def get_close(sym: str, d: date):
        return closes.get((sym, d))

    b = build_equity_point_breakdown(
        on=on,
        previous_on=prev,
        trades_on_date=[],
        cash_events_on_date=[],
        dividend_events_on_date=[],
        open_lots_prev_day=lots,
        violations_on_date=[],
        exempt_matches_on_date=[],
        get_close=get_close,
        delta_account_value=Decimal("180.00"),  # 200 + (-20)
    )
    assert b.delta_unrealized == Decimal("180.00")
    assert len(b.top_movers) == 2
    # Sorted by abs(contribution) desc → AAPL first.
    assert b.top_movers[0].ticker == "AAPL"
    assert b.top_movers[0].contribution == Decimal("200.00")
    assert b.top_movers[1].ticker == "SPY"
    assert b.top_movers[1].contribution == Decimal("-20.00")
    assert b.residual == Decimal("0")


def test_dividend_only_day_attributes_to_dividends():
    on = date(2026, 5, 10)
    div = CashEvent(
        account="Brokerage",
        event_date=on,
        kind="dividend",
        amount=12.34,
        ticker="MSFT",
        description="Qualified dividend",
    )
    b = build_equity_point_breakdown(
        on=on,
        previous_on=date(2026, 5, 9),
        trades_on_date=[],
        cash_events_on_date=[],
        dividend_events_on_date=[div],
        open_lots_prev_day=[],
        violations_on_date=[],
        exempt_matches_on_date=[],
        get_close=lambda sym, d: None,
        delta_account_value=Decimal("12.34"),
    )
    assert b.dividends == Decimal("12.34")
    assert len(b.dividend_events) == 1
    assert b.dividend_events[0].ticker == "MSFT"
    assert b.dividend_events[0].amount == Decimal("12.34")
    assert b.residual == Decimal("0")


def test_wash_sale_violation_on_date_attaches_ref():
    on = date(2026, 5, 10)
    prev = date(2026, 5, 9)
    v = WashSaleViolation(
        id="42",
        loss_trade_id="t1",
        replacement_trade_id="t2",
        loss_sale_date=on,
        triggering_buy_date=on,
        ticker="AAPL",
        disallowed_loss=100.0,
        matched_quantity=10.0,
        confidence="Confirmed",
        kind="deferred",
    )
    b = build_equity_point_breakdown(
        on=on,
        previous_on=prev,
        trades_on_date=[],
        cash_events_on_date=[],
        dividend_events_on_date=[],
        open_lots_prev_day=[],
        violations_on_date=[v],
        exempt_matches_on_date=[],
        get_close=lambda sym, d: None,
        delta_account_value=Decimal("0"),
    )
    assert len(b.wash_events) == 1
    assert b.wash_events[0].kind == "violation"
    assert b.wash_events[0].row_id == 42
    assert b.wash_events[0].ticker == "AAPL"


def test_first_point_in_series_returns_starting_snapshot():
    on = date(2026, 1, 5)
    lots = [
        Lot(
            id="L1",
            trade_id="t-aapl",
            account="Brokerage",
            ticker="AAPL",
            date=date(2026, 1, 5),
            quantity=100.0,
            cost_basis=17000.0,
            adjusted_basis=17000.0,
        ),
    ]
    b = build_equity_point_breakdown(
        on=on,
        previous_on=None,
        trades_on_date=[],
        cash_events_on_date=[],
        dividend_events_on_date=[],
        open_lots_prev_day=lots,
        violations_on_date=[],
        exempt_matches_on_date=[],
        get_close=lambda sym, d: None,
        delta_account_value=Decimal("0"),
        starting_contributed_to_date=Decimal("17500"),
    )
    assert b.is_starting_snapshot is True
    assert b.previous_on is None
    assert b.starting_holdings_count == 1
    assert b.starting_contributed_to_date == Decimal("17500")


def test_missing_close_for_held_ticker_populates_unpriced():
    on = date(2026, 5, 10)
    prev = date(2026, 5, 9)
    lots = [
        Lot(
            id="L1",
            trade_id="t-illiq",
            account="Brokerage",
            ticker="ILLIQ",
            date=date(2026, 1, 5),
            quantity=10.0,
            cost_basis=500.0,
            adjusted_basis=500.0,
        ),
    ]
    b = build_equity_point_breakdown(
        on=on,
        previous_on=prev,
        trades_on_date=[],
        cash_events_on_date=[],
        dividend_events_on_date=[],
        open_lots_prev_day=lots,
        violations_on_date=[],
        exempt_matches_on_date=[],
        get_close=lambda sym, d: None,  # always None
        delta_account_value=Decimal("0"),
    )
    assert b.unpriced_tickers == ("ILLIQ",)
    assert b.unpriced_basis_total == Decimal("500")
    assert b.top_movers == []
    assert b.delta_unrealized == Decimal("0")


def test_unreconciled_delta_exposes_residual():
    on = date(2026, 5, 10)
    prev = date(2026, 5, 9)
    # Caller claims delta=100, but no events explain it → residual=100.
    b = build_equity_point_breakdown(
        on=on,
        previous_on=prev,
        trades_on_date=[],
        cash_events_on_date=[],
        dividend_events_on_date=[],
        open_lots_prev_day=[],
        violations_on_date=[],
        exempt_matches_on_date=[],
        get_close=lambda sym, d: None,
        delta_account_value=Decimal("100"),
    )
    assert b.residual == Decimal("100.00")
