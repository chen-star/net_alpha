import datetime as dt
from decimal import Decimal

from net_alpha.models.domain import Lot, OptionDetails, Trade, WashSaleViolation
from net_alpha.portfolio.pnl import compute_kpis, compute_wash_impact, realized_pl_from_trades
from net_alpha.pricing.provider import Quote


def _trade(**kw):
    defaults = dict(
        id="t1",
        account="Tax",
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
        account="Tax",
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


def test_kpis_zero_when_no_trades():
    k = compute_kpis(trades=[], lots=[], prices={}, period_label="YTD", period=(2026, 2027), account=None)
    assert k.period_realized == Decimal("0")
    assert k.lifetime_realized == Decimal("0")
    assert k.open_position_value == Decimal("0")
    assert k.lifetime_net_pl == Decimal("0")  # 0 realized + 0 unrealized (no missing prices since no lots)


def test_kpis_realized_split_by_period():
    trades = [
        _trade(id="t1", action="Sell", date=dt.date(2025, 6, 10), quantity=10, proceeds=5_000, cost_basis=4_000),
        _trade(id="t2", action="Sell", date=dt.date(2026, 3, 1), quantity=10, proceeds=6_000, cost_basis=4_500),
    ]
    k = compute_kpis(trades=trades, lots=[], prices={}, period_label="YTD", period=(2026, 2027), account=None)
    assert k.period_realized == Decimal("1500")
    assert k.lifetime_realized == Decimal("2500")


def test_kpis_unrealized_uses_prices_when_available():
    lots = [_lot()]
    k = compute_kpis(
        trades=[_trade()],
        lots=lots,
        prices={"SPY": _quote("SPY", 460)},
        period_label="YTD",
        period=(2026, 2027),
        account=None,
    )
    assert k.open_position_value == Decimal("46000")
    assert k.period_unrealized == Decimal("6000")
    assert k.lifetime_unrealized == Decimal("6000")
    assert k.lifetime_net_pl == Decimal("6000")  # 0 realized (Buy only) + 6000 unrealized
    assert k.missing_symbols == ()


def test_kpis_unrealized_none_when_all_lots_unpriced():
    lots = [_lot()]
    k = compute_kpis(trades=[_trade()], lots=lots, prices={}, period_label="YTD", period=(2026, 2027), account=None)
    assert k.open_position_value is None
    assert k.period_unrealized is None
    assert k.lifetime_unrealized is None
    assert k.lifetime_net_pl is None
    assert k.missing_symbols == ("SPY",)


def test_kpis_partial_when_some_lots_unpriced():
    """When some symbols can be priced and others can't, KPIs should reflect
    a partial sum scoped to the priced subset rather than collapsing to None."""
    lots = [
        _lot(id="l1", ticker="SPY", quantity=100.0, cost_basis=40_000.0, adjusted_basis=40_000.0),
        _lot(id="l2", ticker="BITF", quantity=10.0, cost_basis=500.0, adjusted_basis=500.0),
    ]
    trades = [
        _trade(id="t1", ticker="SPY", quantity=100, cost_basis=40_000),
        _trade(id="t2", ticker="BITF", quantity=10, cost_basis=500),
    ]
    k = compute_kpis(
        trades=trades,
        lots=lots,
        prices={"SPY": _quote("SPY", 460)},  # BITF has no quote
        period_label="YTD",
        period=(2026, 2027),
        account=None,
    )
    # Open value reflects only SPY (the priced lot).
    assert k.open_position_value == Decimal("46000")
    # Unrealized = priced_market - priced_basis = 46000 - 40000 = 6000 (BITF excluded).
    assert k.period_unrealized == Decimal("6000")
    assert k.lifetime_unrealized == Decimal("6000")
    assert k.lifetime_net_pl == Decimal("6000")
    assert k.missing_symbols == ("BITF",)


def _violation(loss_date, *, disallowed=100.0, confidence="Confirmed", loss_account="Tax", buy_account="Tax"):
    return WashSaleViolation(
        id="v",
        loss_trade_id="t1",
        replacement_trade_id="t2",
        loss_account=loss_account,
        buy_account=buy_account,
        loss_sale_date=loss_date,
        triggering_buy_date=loss_date,
        ticker="SPY",
        confidence=confidence,
        disallowed_loss=disallowed,
        matched_quantity=10.0,
        source="engine",
    )


def test_wash_impact_period_filters_by_loss_date():
    violations = [
        _violation(dt.date(2026, 3, 1), disallowed=200, confidence="Confirmed"),
        _violation(dt.date(2025, 3, 1), disallowed=300, confidence="Probable"),
    ]
    out = compute_wash_impact(violations=violations, period_label="YTD", period=(2026, 2027), account=None)
    assert out.violation_count == 1
    assert out.disallowed_total == Decimal("200")
    assert out.confirmed_count == 1
    assert out.probable_count == 0


def test_wash_impact_account_filter_matches_either_side():
    v1 = _violation(dt.date(2026, 3, 1), loss_account="IRA", buy_account="IRA")
    v2 = _violation(dt.date(2026, 3, 2), loss_account="Tax", buy_account="Tax")
    v3 = _violation(dt.date(2026, 3, 3), loss_account="IRA", buy_account="Tax")  # cross-account
    out = compute_wash_impact(violations=[v1, v2, v3], period_label="YTD", period=(2026, 2027), account="Tax")
    # v2 (both Tax) and v3 (Tax on buy side) match; v1 (both IRA) does not
    assert out.violation_count == 2


def test_realized_pl_distributes_sto_premium_across_partial_btcs():
    # STO 2 contracts for $1698.67 premium, then close as two separate
    # 1-contract BTCs ($236.66 + $101.66). The premium must be split per
    # contract (not credited in full to each BTC), otherwise lifetime P&L
    # is inflated by the entire STO premium — exactly the TSLA divergence
    # users hit when net-alpha showed $3841.11 vs Schwab's $2142.44.
    opt = OptionDetails(strike=455.0, expiry=dt.date(2025, 10, 24), call_put="C")
    trades = [
        _trade(
            id="t_sto",
            ticker="TSLA",
            action="Sell",
            quantity=2.0,
            proceeds=1698.67,
            cost_basis=None,
            basis_source="option_short_open",
            option_details=opt,
            date=dt.date(2025, 10, 22),
        ),
        _trade(
            id="t_btc1",
            ticker="TSLA",
            action="Buy",
            quantity=1.0,
            proceeds=None,
            cost_basis=236.66,
            basis_source="option_short_close",
            option_details=opt,
            date=dt.date(2025, 10, 23),
        ),
        _trade(
            id="t_btc2",
            ticker="TSLA",
            action="Buy",
            quantity=1.0,
            proceeds=None,
            cost_basis=101.66,
            basis_source="option_short_close",
            option_details=opt,
            date=dt.date(2025, 10, 23),
        ),
    ]
    realized = realized_pl_from_trades(trades, period=None)
    # Correct: 1698.67 - 236.66 - 101.66 = 1360.35
    assert abs(realized - Decimal("1360.35")) < Decimal("0.01")


def test_realized_pl_unequal_btc_quantities_split_premium_proportionally():
    # STO 4 contracts for $400 total premium. Close 3 + 1.
    opt = OptionDetails(strike=100.0, expiry=dt.date(2025, 12, 19), call_put="P")
    trades = [
        _trade(
            id="t_sto",
            action="Sell",
            quantity=4.0,
            proceeds=400.0,
            cost_basis=None,
            basis_source="option_short_open",
            option_details=opt,
            date=dt.date(2025, 6, 1),
        ),
        _trade(
            id="t_btc1",
            action="Buy",
            quantity=3.0,
            proceeds=None,
            cost_basis=120.0,
            basis_source="option_short_close",
            option_details=opt,
            date=dt.date(2025, 7, 1),
        ),
        _trade(
            id="t_btc2",
            action="Buy",
            quantity=1.0,
            proceeds=None,
            cost_basis=30.0,
            basis_source="option_short_close",
            option_details=opt,
            date=dt.date(2025, 7, 15),
        ),
    ]
    realized = realized_pl_from_trades(trades, period=None)
    # 400 (premium) - 120 - 30 = 250
    assert abs(realized - Decimal("250")) < Decimal("0.01")


def test_wash_impact_lifetime_when_period_is_none():
    violations = [
        _violation(dt.date(2024, 6, 1), confidence="Unclear"),
        _violation(dt.date(2025, 6, 1), confidence="Probable"),
    ]
    out = compute_wash_impact(violations=violations, period_label="Lifetime", period=None, account=None)
    assert out.violation_count == 2
    assert out.unclear_count == 1
    assert out.probable_count == 1
