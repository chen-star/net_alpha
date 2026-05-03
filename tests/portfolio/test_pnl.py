import datetime as dt
from decimal import Decimal

from net_alpha.models.domain import Lot, OptionDetails, Trade, WashSaleViolation
from net_alpha.models.realized_gl import RealizedGLLot
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


def test_kpis_open_value_excludes_already_sold_lots():
    """Regression: lot.quantity is the original buy size and never decremented
    when the user sells. compute_kpis must FIFO-consume lots against sell
    trades, otherwise open_position_value double-counts shares the user has
    already disposed of."""
    lots = [
        _lot(id="l1", quantity=100.0, cost_basis=40_000.0, adjusted_basis=40_000.0),
        _lot(id="l2", date=dt.date(2025, 3, 1), quantity=50.0, cost_basis=22_000.0, adjusted_basis=22_000.0),
    ]
    trades = [
        _trade(id="tb1", action="Buy", quantity=100, cost_basis=40_000),
        _trade(id="tb2", action="Buy", date=dt.date(2025, 3, 1), quantity=50, cost_basis=22_000),
        # Sell 100: should fully consume the first lot via FIFO.
        _trade(id="ts1", action="Sell", date=dt.date(2025, 6, 1), quantity=100, proceeds=46_000, cost_basis=40_000),
    ]
    k = compute_kpis(
        trades=trades,
        lots=lots,
        prices={"SPY": _quote("SPY", 460)},
        period_label="YTD",
        period=(2026, 2027),
        account=None,
    )
    # Only the second lot (50 shares) remains open after the FIFO sell.
    assert k.open_position_value == Decimal("23000")  # 50 * 460
    # Unrealized = market - prorated_basis = 23000 - 22000 = 1000.
    assert k.period_unrealized == Decimal("1000")
    assert k.lifetime_unrealized == Decimal("1000")


def test_kpis_open_value_honors_gl_closures():
    """When a Realized G/L CSV reports a closure that has no matching trade
    row (Schwab logs option expirations / corporate actions only in GL),
    compute_kpis must still treat the lot as closed."""
    lots = [_lot(id="l1", quantity=100.0, cost_basis=40_000.0, adjusted_basis=40_000.0)]
    trades = [_trade(id="tb1", action="Buy", quantity=100, cost_basis=40_000)]
    gl_lots = [
        RealizedGLLot(
            id="g1",
            account_display="Tax",
            symbol_raw="SPY",
            ticker="SPY",
            opened_date=dt.date(2025, 1, 15),
            closed_date=dt.date(2025, 6, 1),
            quantity=100.0,
            proceeds=46_000.0,
            cost_basis=40_000.0,
            unadjusted_cost_basis=40_000.0,
            wash_sale=False,
            disallowed_loss=0.0,
            term="Short",
        ),
    ]
    k = compute_kpis(
        trades=trades,
        lots=lots,
        prices={"SPY": _quote("SPY", 460)},
        period_label="YTD",
        period=(2026, 2027),
        account=None,
        gl_lots=gl_lots,
    )
    assert k.open_position_value == Decimal("0")
    # No open lots are priced, so unrealized collapses too — unrealized for an
    # empty open subset is just 0 (the all_unpriced guard only fires when there
    # are equity lots that we couldn't price).
    assert k.period_unrealized == Decimal("0")


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


def _gl_lot(**kw):
    defaults = dict(
        account_display="Tax",
        symbol_raw="OSCR 01/16/2026 25.00 C",
        ticker="OSCR",
        closed_date=dt.date(2026, 1, 16),
        opened_date=dt.date(2025, 10, 10),
        quantity=1.0,
        proceeds=0.0,
        cost_basis=258.66,
        unadjusted_cost_basis=258.66,
        wash_sale=False,
        disallowed_loss=0.0,
        term="Short Term",
        option_strike=25.0,
        option_expiry="2026-01-16",
        option_call_put="C",
    )
    defaults.update(kw)
    return RealizedGLLot(**defaults)


def test_realized_pl_synthesizes_long_option_expiry_from_gl():
    # Schwab "Transactions" CSV records "Expired" rows that the parser drops,
    # leaving the trades table without a Sell-to-Close counterpart for long
    # options that expired worthless. Without GL data, those losses are
    # silently missed by realized_pl_from_trades. The Realized G/L CSV
    # records the closure (proceeds=0, cost=N), so we reconcile from there.
    #
    # Real-world OSCR repro: 25C 01/16/2026 (qty 1, basis 258.66) and 30C
    # 01/16/2026 (qty 2, basis 160.66 each) all expired on 2026-01-16.
    # Trade table has only the BTOs. Schwab GL has the closures. Net-alpha
    # must include them in YTD/lifetime realized P&L.
    opt_25c = OptionDetails(strike=25.0, expiry=dt.date(2026, 1, 16), call_put="C")
    opt_30c = OptionDetails(strike=30.0, expiry=dt.date(2026, 1, 16), call_put="C")
    trades = [
        # BTO of long 25C on 2025-10-10 (cost 258.66) — no STC counterpart
        _trade(
            id="bto_25c",
            ticker="OSCR",
            action="Buy",
            quantity=1.0,
            proceeds=None,
            cost_basis=258.66,
            basis_source="unknown",
            option_details=opt_25c,
            date=dt.date(2025, 10, 10),
        ),
        # BTO of long 30C #1 on 2025-10-10
        _trade(
            id="bto_30c_a",
            ticker="OSCR",
            action="Buy",
            quantity=1.0,
            proceeds=None,
            cost_basis=160.66,
            basis_source="unknown",
            option_details=opt_30c,
            date=dt.date(2025, 10, 10),
        ),
        # BTO of long 30C #2 on 2025-10-20
        _trade(
            id="bto_30c_b",
            ticker="OSCR",
            action="Buy",
            quantity=1.0,
            proceeds=None,
            cost_basis=160.66,
            basis_source="unknown",
            option_details=opt_30c,
            date=dt.date(2025, 10, 20),
        ),
    ]
    gl_lots = [
        _gl_lot(option_strike=25.0, cost_basis=258.66, opened_date=dt.date(2025, 10, 10)),
        _gl_lot(
            option_strike=30.0,
            symbol_raw="OSCR 01/16/2026 30.00 C",
            cost_basis=160.66,
            opened_date=dt.date(2025, 10, 10),
        ),
        _gl_lot(
            option_strike=30.0,
            symbol_raw="OSCR 01/16/2026 30.00 C",
            cost_basis=160.66,
            opened_date=dt.date(2025, 10, 20),
        ),
    ]
    # YTD 2026 realized: -258.66 -160.66 -160.66 = -579.98
    realized_ytd = realized_pl_from_trades(trades, period=(2026, 2027), gl_lots=gl_lots)
    assert abs(realized_ytd - Decimal("-579.98")) < Decimal("0.01")
    # Lifetime same: no other realizations
    realized_life = realized_pl_from_trades(trades, period=None, gl_lots=gl_lots)
    assert abs(realized_life - Decimal("-579.98")) < Decimal("0.01")


def test_realized_pl_does_not_double_count_when_gl_pairs_with_trade_close():
    # The Schwab GL CSV records the same close events as the trade-side STCs
    # and BTCs already in the trades table. We must NOT double-count: when a
    # GL lot has a matching close trade (STC or BTC) on the same / adjacent
    # date for the same option key, the trade-side already accounted for it.
    opt = OptionDetails(strike=25.0, expiry=dt.date(2026, 1, 16), call_put="C")
    trades = [
        _trade(
            id="bto",
            ticker="OSCR",
            action="Buy",
            quantity=1.0,
            proceeds=None,
            cost_basis=185.66,
            basis_source="unknown",
            option_details=opt,
            date=dt.date(2025, 10, 1),
        ),
        # STC on 2025-10-03 with cost_basis from g_l → realized P&L = +98.68
        _trade(
            id="stc",
            ticker="OSCR",
            action="Sell",
            quantity=1.0,
            proceeds=284.34,
            cost_basis=185.66,
            basis_source="g_l",
            option_details=opt,
            date=dt.date(2025, 10, 3),
        ),
    ]
    # Schwab GL row for the same close (closed_date matches trade date)
    gl_lots = [
        _gl_lot(
            closed_date=dt.date(2025, 10, 3),
            opened_date=dt.date(2025, 10, 1),
            proceeds=284.34,
            cost_basis=185.66,
        ),
    ]
    realized = realized_pl_from_trades(trades, period=None, gl_lots=gl_lots)
    # Only count it once: 284.34 - 185.66 = 98.68 (NOT 197.36)
    assert abs(realized - Decimal("98.68")) < Decimal("0.01")


def test_realized_pl_pairs_btc_with_gl_at_settlement_offset():
    # Schwab GL `closed_date` is settle date (T+1) while the BTC trade row
    # carries the actual trade date. Pairing must tolerate a ±1 day gap so
    # the BTC's premium-share P&L isn't doubled by a "synthetic" GL close.
    opt = OptionDetails(strike=17.0, expiry=dt.date(2025, 8, 15), call_put="P")
    trades = [
        # STO premium received
        _trade(
            id="sto",
            ticker="OSCR",
            action="Sell",
            quantity=1.0,
            proceeds=269.34,
            cost_basis=None,
            basis_source="option_short_open",
            option_details=opt,
            date=dt.date(2025, 7, 2),
        ),
        # BTC on 2025-08-07 closes the short (paired premium realized)
        _trade(
            id="btc",
            ticker="OSCR",
            action="Buy",
            quantity=1.0,
            proceeds=None,
            cost_basis=212.66,
            basis_source="option_short_close",
            option_details=opt,
            date=dt.date(2025, 8, 7),
        ),
    ]
    # Schwab GL records closed_date as T+1 settlement
    gl_lots = [
        _gl_lot(
            symbol_raw="OSCR 08/15/2025 17.00 P",
            ticker="OSCR",
            closed_date=dt.date(2025, 8, 8),
            opened_date=dt.date(2025, 7, 2),
            proceeds=269.34,
            cost_basis=212.66,
            option_strike=17.0,
            option_expiry="2025-08-15",
            option_call_put="P",
        ),
    ]
    realized = realized_pl_from_trades(trades, period=None, gl_lots=gl_lots)
    # Pair-counted once: 269.34 - 212.66 = 56.68. Without ±1-day pairing
    # the GL would synthesize a duplicate +56.68.
    assert abs(realized - Decimal("56.68")) < Decimal("0.01")


def test_compute_kpis_emits_economic_realized_alongside_recognized():
    # KpiSet exposes both views: tax-recognized (the main number, matches
    # Schwab UI) and economic (the actual cash netted, recognized minus the
    # wash-sale add-back). The Realized P/L tile renders both.
    gl_lots = [
        _gl_lot(
            symbol_raw="PANW",
            ticker="PANW",
            closed_date=dt.date(2025, 8, 12),
            opened_date=dt.date(2025, 8, 5),
            proceeds=199.34,
            cost_basis=255.66,
            unadjusted_cost_basis=255.66,
            wash_sale=True,
            disallowed_loss=56.32,
            option_strike=None,
            option_expiry=None,
            option_call_put=None,
        ),
    ]
    k = compute_kpis(
        trades=[],
        lots=[],
        prices={},
        period_label="2025",
        period=(2025, 2026),
        account=None,
        gl_lots=gl_lots,
    )
    # Recognized = (proc - cb) + disallowed = -56.32 + 56.32 = 0
    assert abs(k.period_realized - Decimal("0")) < Decimal("0.01")
    # Economic = (proc - cb) = -56.32 (actual cash loss before wash adjustment)
    assert abs(k.period_realized_economic - Decimal("-56.32")) < Decimal("0.01")


def test_realized_pl_adds_back_wash_sale_disallowed_loss():
    # Real-world PANW repro: 2 closes — one with a $56.32 loss fully disallowed
    # by §1091, one with a $102.36 gain. Schwab's UI and Form 8949 add the
    # disallowed loss back to the lot's realized P&L (the loss shifts to the
    # replacement lot's basis), so the recognized period total is +$102.36, not
    # the economic +$46.04.
    gl_lots = [
        _gl_lot(
            symbol_raw="PANW",
            ticker="PANW",
            closed_date=dt.date(2025, 8, 12),
            opened_date=dt.date(2025, 8, 5),
            proceeds=199.34,
            cost_basis=255.66,
            unadjusted_cost_basis=255.66,
            wash_sale=True,
            disallowed_loss=56.32,
            option_strike=None,
            option_expiry=None,
            option_call_put=None,
        ),
        _gl_lot(
            symbol_raw="PANW",
            ticker="PANW",
            closed_date=dt.date(2025, 8, 13),
            opened_date=dt.date(2025, 8, 6),
            proceeds=299.34,
            cost_basis=196.98,
            unadjusted_cost_basis=196.98,
            wash_sale=False,
            disallowed_loss=0.0,
            option_strike=None,
            option_expiry=None,
            option_call_put=None,
        ),
    ]
    realized = realized_pl_from_trades([], period=(2025, 2026), gl_lots=gl_lots)
    # 102.36 (gain) + 0 (loss recognized as zero, $56.32 shifted to replacement)
    assert abs(realized - Decimal("102.36")) < Decimal("0.01")


def test_realized_pl_pairs_btc_across_weekend_settlement():
    # Real-world UUUU repro: a BTC traded on a Friday settles Monday — a
    # 3-calendar-day gap. With a 2-day tolerance the GL synth path counted
    # the closure a second time, inflating YTD realized by the full premium
    # delta. Tolerance must cover Fri→Mon (3 days) and Fri→Tue across a
    # Monday holiday (4 days).
    opt = OptionDetails(strike=20.0, expiry=dt.date(2026, 1, 16), call_put="P")
    trades = [
        _trade(
            id="sto",
            ticker="UUUU",
            action="Sell",
            quantity=1.0,
            proceeds=486.34,
            cost_basis=None,
            basis_source="option_short_open",
            option_details=opt,
            date=dt.date(2025, 12, 11),
        ),
        # BTC on Fri 2026-01-09; Schwab settles it Mon 2026-01-12 (3-day gap).
        _trade(
            id="btc",
            ticker="UUUU",
            action="Buy",
            quantity=1.0,
            proceeds=None,
            cost_basis=140.66,
            basis_source="option_short_close",
            option_details=opt,
            date=dt.date(2026, 1, 9),
        ),
    ]
    gl_lots = [
        _gl_lot(
            symbol_raw="UUUU 01/16/2026 20.00 P",
            ticker="UUUU",
            closed_date=dt.date(2026, 1, 12),  # Monday settlement after Friday trade
            opened_date=dt.date(2025, 12, 12),
            proceeds=486.34,
            cost_basis=140.66,
            option_strike=20.0,
            option_expiry="2026-01-16",
            option_call_put="P",
        ),
    ]
    realized = realized_pl_from_trades(trades, period=(2026, 2027), gl_lots=gl_lots)
    # Counted once: 486.34 - 140.66 = 345.68. With the old 2-day tolerance
    # the GL would have added a duplicate 345.68 → 691.36.
    assert abs(realized - Decimal("345.68")) < Decimal("0.01")


def test_realized_pl_period_filter_uses_gl_closed_date():
    # GL-synthesized closures must respect the period filter using the GL's
    # closed_date, not the trade's BTO date. An OSCR call bought in 2025 that
    # expired in 2026 belongs to YTD 2026, not YTD 2025.
    opt = OptionDetails(strike=25.0, expiry=dt.date(2026, 1, 16), call_put="C")
    trades = [
        _trade(
            id="bto",
            ticker="OSCR",
            action="Buy",
            quantity=1.0,
            proceeds=None,
            cost_basis=258.66,
            basis_source="unknown",
            option_details=opt,
            date=dt.date(2025, 10, 10),
        ),
    ]
    gl_lots = [_gl_lot(opened_date=dt.date(2025, 10, 10))]
    # YTD 2025 should NOT include the 2026 expiry
    assert realized_pl_from_trades(trades, period=(2025, 2026), gl_lots=gl_lots) == Decimal("0")
    # YTD 2026 should
    realized = realized_pl_from_trades(trades, period=(2026, 2027), gl_lots=gl_lots)
    assert abs(realized - Decimal("-258.66")) < Decimal("0.01")


def test_wash_impact_lifetime_when_period_is_none():
    violations = [
        _violation(dt.date(2024, 6, 1), confidence="Unclear"),
        _violation(dt.date(2025, 6, 1), confidence="Probable"),
    ]
    out = compute_wash_impact(violations=violations, period_label="Lifetime", period=None, account=None)
    assert out.violation_count == 2
    assert out.unclear_count == 1
    assert out.probable_count == 1
