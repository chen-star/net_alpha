import datetime as dt
from decimal import Decimal

from net_alpha.models.domain import Lot, Trade
from net_alpha.portfolio.positions import compute_open_positions
from net_alpha.pricing.provider import Quote


def _trade(**kw):
    defaults = dict(
        id="t1",
        account="Schwab Tax",
        date=dt.date(2025, 1, 15),
        ticker="SPY",
        action="Buy",
        quantity=100.0,
        proceeds=None,
        cost_basis=40_000.0,
        basis_unknown=False,
        option_details=None,
    )
    defaults.update(kw)
    return Trade(**defaults)


def _lot(**kw):
    defaults = dict(
        id="l1",
        trade_id="t1",
        account="Schwab Tax",
        date=dt.date(2025, 1, 15),
        ticker="SPY",
        quantity=100.0,
        cost_basis=40_000.0,
        adjusted_basis=40_000.0,
        option_details=None,
    )
    defaults.update(kw)
    return Lot(**defaults)


def _quote(symbol, price):
    return Quote(symbol=symbol, price=Decimal(str(price)), as_of=dt.datetime.now(dt.UTC), source="yahoo")


def test_single_lot_single_buy_no_sells():
    trades = [_trade()]
    lots = [_lot()]
    rows = compute_open_positions(
        trades=trades, lots=lots, prices={"SPY": _quote("SPY", 460)}, period=None, account=None
    )
    assert len(rows) == 1
    r = rows[0]
    assert r.symbol == "SPY"
    assert r.qty == Decimal("100")
    assert r.market_value == Decimal("46000")
    assert r.open_cost == Decimal("40000")
    assert r.avg_basis == Decimal("400")
    assert r.cash_sunk_per_share == Decimal("400")  # no sells → buys / qty
    assert r.unrealized_pl == Decimal("6000")


def test_position_with_sell_reduces_cash_sunk():
    trades = [
        _trade(id="t1", quantity=100.0, cost_basis=40_000.0),
        _trade(
            id="t2", action="Sell", quantity=50.0, proceeds=25_000.0, cost_basis=20_000.0, date=dt.date(2025, 6, 10)
        ),
    ]
    # Lot stored with full original buy quantity — engine never decrements lots
    # when sells happen; compute_open_positions FIFO-consumes them at read time.
    lots = [_lot(quantity=100.0, cost_basis=40_000.0, adjusted_basis=40_000.0)]
    rows = compute_open_positions(
        trades=trades, lots=lots, prices={"SPY": _quote("SPY", 520)}, period=None, account=None
    )
    r = rows[0]
    assert r.qty == Decimal("50")
    assert r.open_cost == Decimal("20000")
    assert r.cash_sunk_per_share == Decimal("300")  # (40000 − 25000) / 50


def test_position_fully_closed_by_sells_excluded_from_open():
    trades = [
        _trade(id="t1", quantity=100.0, cost_basis=40_000.0),
        _trade(
            id="t2", action="Sell", quantity=100.0, proceeds=50_000.0, cost_basis=40_000.0, date=dt.date(2025, 6, 10)
        ),
    ]
    lots = [_lot(quantity=100.0, cost_basis=40_000.0, adjusted_basis=40_000.0)]
    rows = compute_open_positions(
        trades=trades, lots=lots, prices={"SPY": _quote("SPY", 520)}, period=None, account=None
    )
    # Fully closed → no open row.
    assert rows == []


def test_position_closed_via_gl_when_trade_sells_missing():
    # Simulates: user imported Realized G/L but only partial Transaction History
    # — buys are present, sells are missing from trades. GL closures should
    # still drive the open quantity down to zero.
    trades = [_trade(id="t1", quantity=100.0, cost_basis=40_000.0)]
    lots = [_lot(quantity=100.0, cost_basis=40_000.0, adjusted_basis=40_000.0)]
    rows = compute_open_positions(
        trades=trades,
        lots=lots,
        prices={"SPY": _quote("SPY", 520)},
        period=None,
        account=None,
        gl_closures={("Schwab Tax", "SPY"): 100.0},
    )
    assert rows == []


def test_gl_closures_take_precedence_when_larger_than_trade_sells():
    trades = [
        _trade(id="t1", quantity=100.0, cost_basis=40_000.0),
        _trade(id="t2", action="Sell", quantity=10.0, proceeds=5_000.0, cost_basis=4_000.0, date=dt.date(2025, 6, 10)),
    ]
    lots = [_lot(quantity=100.0, cost_basis=40_000.0, adjusted_basis=40_000.0)]
    # GL says 80 closed; trades say 10 — GL wins (canonical when more complete).
    rows = compute_open_positions(
        trades=trades,
        lots=lots,
        prices={"SPY": _quote("SPY", 520)},
        period=None,
        account=None,
        gl_closures={("Schwab Tax", "SPY"): 80.0},
    )
    assert len(rows) == 1
    assert rows[0].qty == Decimal("20")


def test_missing_price_yields_none_market_value_and_unrealized():
    trades = [_trade()]
    lots = [_lot()]
    rows = compute_open_positions(trades=trades, lots=lots, prices={}, period=None, account=None)
    r = rows[0]
    assert r.market_value is None
    assert r.unrealized_pl is None


def test_account_filter_drops_other_accounts():
    trades = [
        _trade(id="t1", account="Schwab Tax"),
        _trade(id="t2", account="Schwab IRA", quantity=10.0, cost_basis=4_000.0),
    ]
    lots = [
        _lot(id="l1", account="Schwab Tax"),
        _lot(id="l2", account="Schwab IRA", quantity=10.0, cost_basis=4_000.0, adjusted_basis=4_000.0),
    ]
    rows = compute_open_positions(
        trades=trades, lots=lots, prices={"SPY": _quote("SPY", 460)}, period=None, account="Schwab Tax"
    )
    assert len(rows) == 1
    assert rows[0].qty == Decimal("100")


def test_accounts_field_lists_all_holders():
    trades = [
        _trade(id="t1", account="Schwab Tax"),
        _trade(id="t2", account="Schwab IRA", quantity=10.0, cost_basis=4_000.0),
    ]
    lots = [
        _lot(id="l1", account="Schwab Tax"),
        _lot(id="l2", account="Schwab IRA", quantity=10.0, cost_basis=4_000.0, adjusted_basis=4_000.0),
    ]
    rows = compute_open_positions(
        trades=trades, lots=lots, prices={"SPY": _quote("SPY", 460)}, period=None, account=None
    )
    r = rows[0]
    assert set(r.accounts) == {"Schwab Tax", "Schwab IRA"}


def test_period_filter_scopes_realized_pl():
    trades = [
        _trade(id="t1", quantity=100.0, cost_basis=40_000.0),  # buy 2025-01-15
        _trade(
            id="t2", action="Sell", quantity=30.0, proceeds=15_000.0, cost_basis=12_000.0, date=dt.date(2025, 6, 10)
        ),  # +3000 in 2025
        _trade(
            id="t3", action="Sell", quantity=20.0, proceeds=10_000.0, cost_basis=8_000.0, date=dt.date(2026, 3, 1)
        ),  # +2000 in 2026
    ]
    lots = [_lot(quantity=100.0, cost_basis=40_000.0, adjusted_basis=40_000.0)]
    # YTD 2026 only: should see only the +2000 sell
    rows = compute_open_positions(
        trades=trades,
        lots=lots,
        prices={"SPY": _quote("SPY", 460)},
        period=(2026, 2027),
        account=None,
    )
    assert rows[0].realized_pl == Decimal("2000")
    # Lifetime: should see both sells = +5000
    rows = compute_open_positions(
        trades=trades,
        lots=lots,
        prices={"SPY": _quote("SPY", 460)},
        period=None,
        account=None,
    )
    assert rows[0].realized_pl == Decimal("5000")


def test_option_lots_excluded_from_qty_and_basis():
    from net_alpha.models.domain import OptionDetails

    option_details = OptionDetails(strike=500.0, expiry=dt.date(2026, 6, 20), call_put="C")
    lots = [
        _lot(id="l1"),  # equity SPY
        _lot(id="l2", quantity=1.0, cost_basis=500.0, adjusted_basis=500.0, option_details=option_details),
    ]
    rows = compute_open_positions(
        trades=[_trade()],
        lots=lots,
        prices={"SPY": _quote("SPY", 460)},
        period=None,
        account=None,
    )
    # Only the equity lot contributes to qty
    assert rows[0].qty == Decimal("100")
    assert rows[0].open_cost == Decimal("40000")


def test_open_short_put_only_surfaces_underlying_with_zero_qty():
    """A ticker with no equity buys but an open Sell-to-Open put (e.g. UUUU)
    must still appear as a row so the user can drill into it from /holdings.
    """
    from net_alpha.models.domain import OptionDetails

    sto = _trade(
        id="t-sto",
        ticker="UUUU",
        action="Sell",
        quantity=1.0,
        proceeds=486.34,
        cost_basis=None,
        basis_source="option_short_open",
        option_details=OptionDetails(strike=20.0, expiry=dt.date(2026, 1, 16), call_put="P"),
    )
    rows = compute_open_positions(trades=[sto], lots=[], prices={}, period=None, account=None)
    assert len(rows) == 1
    r = rows[0]
    assert r.symbol == "UUUU"
    assert r.qty == 0
    assert r.open_option_contracts == Decimal("1")


def test_round_trip_short_put_does_not_surface_after_close():
    """STO followed by BTC of the same option contract → net 0 → no row."""
    from net_alpha.models.domain import OptionDetails

    opt = OptionDetails(strike=20.0, expiry=dt.date(2026, 1, 16), call_put="P")
    sto = _trade(
        id="t-sto",
        ticker="UUUU",
        action="Sell",
        quantity=1.0,
        proceeds=486.34,
        cost_basis=None,
        basis_source="option_short_open",
        option_details=opt,
    )
    btc = _trade(
        id="t-btc",
        ticker="UUUU",
        action="Buy",
        quantity=1.0,
        proceeds=None,
        cost_basis=140.66,
        basis_source="option_short_close",
        option_details=opt,
        date=dt.date(2026, 1, 9),
    )
    rows = compute_open_positions(trades=[sto, btc], lots=[], prices={}, period=None, account=None)
    assert rows == []


def test_open_long_call_alongside_equity_shows_both_signals():
    """Underlying with both an open equity lot AND an open BTO call: the
    equity row should appear normally with `open_option_contracts` set so
    the badge can render alongside qty."""
    from net_alpha.models.domain import OptionDetails

    eq_buy = _trade(id="t-eq", ticker="TSLA", action="Buy", quantity=1.0, cost_basis=300.0)
    eq_lot = _lot(id="l-eq", trade_id="t-eq", ticker="TSLA", quantity=1.0, cost_basis=300.0, adjusted_basis=300.0)
    bto = _trade(
        id="t-bto",
        ticker="TSLA",
        action="Buy",
        quantity=1.0,
        cost_basis=4450.66,
        option_details=OptionDetails(strike=400.0, expiry=dt.date(2026, 6, 18), call_put="C"),
        date=dt.date(2025, 7, 14),
    )
    rows = compute_open_positions(
        trades=[eq_buy, bto], lots=[eq_lot], prices={"TSLA": _quote("TSLA", 350)}, period=None, account=None
    )
    [tsla] = rows
    assert tsla.qty == Decimal("1")
    assert tsla.open_option_contracts == Decimal("1")


def test_open_option_counter_subtracts_gl_closures():
    """A BTO with no matching STC trade but a GL closure (e.g. expired
    worthless, only Schwab's GL records the close) must not surface as an
    open contract — otherwise tickers like AES/NVDA appear as 'open opt'
    long after they've actually closed."""
    from datetime import date as _d

    from net_alpha.models.domain import OptionDetails
    from net_alpha.portfolio.positions import compute_open_option_contracts

    bto = _trade(
        id="t-bto",
        ticker="HIMS",
        action="Buy",
        quantity=1.0,
        cost_basis=750.66,
        option_details=OptionDetails(strike=70.0, expiry=_d(2026, 1, 16), call_put="C"),
        date=_d(2025, 10, 2),
    )
    # Without GL augmentation, this BTO looks open.
    no_gl = compute_open_option_contracts([bto])
    assert no_gl == {"HIMS": Decimal("1")}

    # GL records the same contract closing (expired worthless on 2026-01-16).
    gl = {("HIMS", 70.0, _d(2026, 1, 16), "C"): 1.0}
    with_gl = compute_open_option_contracts([bto], gl_option_closures=gl)
    assert with_gl == {}


def test_open_option_counter_subtracts_gl_for_short_too():
    """Symmetric: a STO whose close is only in GL (e.g. assigned put closure
    Schwab logged as a GL row) must zero out — not stay surfaced as a short."""
    from datetime import date as _d

    from net_alpha.models.domain import OptionDetails
    from net_alpha.portfolio.positions import compute_open_option_contracts

    sto = _trade(
        id="t-sto",
        ticker="UUUU",
        action="Sell",
        quantity=1.0,
        proceeds=486.34,
        cost_basis=None,
        basis_source="option_short_open",
        option_details=OptionDetails(strike=20.0, expiry=_d(2026, 1, 16), call_put="P"),
    )
    no_gl = compute_open_option_contracts([sto])
    assert no_gl == {"UUUU": Decimal("1")}

    gl = {("UUUU", 20.0, _d(2026, 1, 16), "P"): 1.0}
    with_gl = compute_open_option_contracts([sto], gl_option_closures=gl)
    assert with_gl == {}


def test_open_lots_view_filters_closed_options_via_gl():
    """Long-option BTO with no STC trade but a GL closure (expired worthless)
    must NOT appear in the lots view. Without this, /ticker/NVDA showed the
    NVDA 220C 12/19 BTO as still open even though GL records it closed."""
    from datetime import date as _d

    from net_alpha.models.domain import OptionDetails
    from net_alpha.portfolio.positions import open_lots_view

    bto = _trade(
        id="t-bto",
        ticker="NVDA",
        action="Buy",
        quantity=1.0,
        cost_basis=180.66,
        option_details=OptionDetails(strike=220.0, expiry=_d(2025, 12, 19), call_put="C"),
        date=_d(2025, 11, 20),
    )
    lot = _lot(
        id="l-bto",
        trade_id="t-bto",
        ticker="NVDA",
        date=_d(2025, 11, 20),
        quantity=1.0,
        cost_basis=180.66,
        adjusted_basis=180.66,
        option_details=OptionDetails(strike=220.0, expiry=_d(2025, 12, 19), call_put="C"),
    )
    # Without GL → still appears open (FIFO has nothing to consume against).
    assert len(open_lots_view(lots=[lot], trades=[bto])) == 1

    gl = {("Schwab Tax", "NVDA", 220.0, _d(2025, 12, 19), "C"): 1.0}
    out = open_lots_view(lots=[lot], trades=[bto], gl_option_closures=gl)
    assert out == []


def test_open_lots_view_handles_corporate_action_ticker_change():
    """A BTO under ticker 'GME' followed by an STC trade (or GL closure) under
    Schwab's post-corp-action symbol 'GME1' represents the same economic
    position. The lot must be consumed even though the closing event has a
    different ticker string.
    """
    from datetime import date as _d

    from net_alpha.models.domain import OptionDetails
    from net_alpha.portfolio.positions import open_lots_view

    opt = OptionDetails(strike=30.0, expiry=_d(2026, 1, 16), call_put="C")
    bto = _trade(
        id="t-bto",
        ticker="GME",  # original symbol
        action="Buy",
        quantity=1.0,
        cost_basis=290.66,
        option_details=opt,
        date=_d(2025, 10, 2),
    )
    stc = _trade(
        id="t-stc",
        ticker="GME1",  # post-corp-action symbol
        action="Sell",
        quantity=1.0,
        proceeds=164.34,
        cost_basis=290.66,
        option_details=opt,
        date=_d(2025, 10, 7),
    )
    lot = _lot(
        id="l-bto",
        trade_id="t-bto",
        ticker="GME",
        date=_d(2025, 10, 2),
        quantity=1.0,
        cost_basis=290.66,
        adjusted_basis=290.66,
        option_details=opt,
    )
    out = open_lots_view(lots=[lot], trades=[bto, stc])
    assert out == []
