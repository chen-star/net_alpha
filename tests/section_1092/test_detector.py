from datetime import date
from decimal import Decimal

from net_alpha.models.domain import Lot, OptionDetails, Trade
from net_alpha.section_1092.detector import detect_offsetting_groups


def _long_call_trade(*, ticker="AAPL", strike=180.0, expiry=date(2026, 12, 18)) -> Trade:
    return Trade(
        id=f"call-{ticker}-{strike}",
        date=date(2026, 1, 5),
        account="schwab/personal",
        ticker=ticker,
        action="Buy",
        quantity=1,
        proceeds=None,
        cost_basis=500.0,
        option_details=OptionDetails(strike=strike, expiry=expiry, call_put="C"),
    )


def _long_put_trade(*, ticker="AAPL", strike=180.0, expiry=date(2026, 12, 18)) -> Trade:
    return Trade(
        id=f"put-{ticker}-{strike}",
        date=date(2026, 1, 10),
        account="schwab/personal",
        ticker=ticker,
        action="Buy",
        quantity=1,
        proceeds=None,
        cost_basis=400.0,
        option_details=OptionDetails(strike=strike, expiry=expiry, call_put="P"),
    )


def test_no_open_positions_returns_empty():
    assert detect_offsetting_groups(trades=[], lots=[]) == []


def test_lone_long_call_no_group():
    call = _long_call_trade()
    lots = [Lot.from_trade(call)]
    assert detect_offsetting_groups(trades=[call], lots=lots) == []


def test_long_call_and_long_put_same_underlying_emits_literal_straddle():
    call = _long_call_trade()
    put = _long_put_trade()
    lots = [Lot.from_trade(call), Lot.from_trade(put)]

    groups = detect_offsetting_groups(trades=[call, put], lots=lots)
    assert len(groups) == 1
    g = groups[0]
    assert g.kind == "literal_straddle"
    assert g.ticker == "AAPL"
    assert g.confidence == "Confirmed"
    assert g.rule_citation.startswith("IRC §1092")
    assert {p.kind for p in g.positions} == {"long_call", "long_put"}


def test_call_and_put_on_different_underlyings_no_group():
    call_aapl = _long_call_trade(ticker="AAPL")
    put_msft = _long_put_trade(ticker="MSFT")
    lots = [Lot.from_trade(call_aapl), Lot.from_trade(put_msft)]
    assert detect_offsetting_groups(trades=[call_aapl, put_msft], lots=lots) == []


def test_call_and_put_in_different_accounts_no_group():
    call = _long_call_trade()
    put = _long_put_trade()
    put.account = "fidelity/personal"  # different account
    put_lot = Lot.from_trade(put)
    lots = [Lot.from_trade(call), put_lot]
    # v1 scope: §1092 offsets within a single taxpayer/account boundary.
    # Cross-account offsets would matter for real §1092 attribution but we
    # ship the conservative-narrow version in v1.
    groups = detect_offsetting_groups(trades=[call, put], lots=lots)
    assert groups == []


def test_closed_call_does_not_form_group():
    call = _long_call_trade()
    sell_call = Trade(
        id="call-sell",
        date=date(2026, 2, 1),
        account="schwab/personal",
        ticker="AAPL",
        action="Sell",
        quantity=1,
        proceeds=600.0,
        cost_basis=None,
        option_details=call.option_details,
    )
    put = _long_put_trade()
    lots = [Lot.from_trade(call), Lot.from_trade(put)]
    # Call has been sold-to-close — only the put remains open.
    groups = detect_offsetting_groups(trades=[call, sell_call, put], lots=lots)
    assert groups == []


def test_long_stock_and_long_put_emits_married_put():
    stock_buy = Trade(
        id="stk-1",
        date=date(2026, 1, 3),
        account="schwab/personal",
        ticker="AAPL",
        action="Buy",
        quantity=100,
        proceeds=None,
        cost_basis=18000.0,
        option_details=None,
    )
    put = _long_put_trade()  # AAPL put
    lots = [Lot.from_trade(stock_buy), Lot.from_trade(put)]

    groups = detect_offsetting_groups(trades=[stock_buy, put], lots=lots)
    kinds = {g.kind for g in groups}
    assert "married_put" in kinds
    married = next(g for g in groups if g.kind == "married_put")
    assert {p.kind for p in married.positions} == {"long_stock", "long_put"}
    assert married.rule_citation.startswith("IRC §1092")


def test_long_stock_alone_no_married_put():
    stock_buy = Trade(
        id="stk-1",
        date=date(2026, 1, 3),
        account="schwab/personal",
        ticker="AAPL",
        action="Buy",
        quantity=100,
        proceeds=None,
        cost_basis=18000.0,
        option_details=None,
    )
    lots = [Lot.from_trade(stock_buy)]
    assert detect_offsetting_groups(trades=[stock_buy], lots=lots) == []


def _short_call_sto(*, ticker="AAPL", strike=200.0, expiry=date(2026, 6, 19), proceeds=300.0) -> Trade:
    return Trade(
        id=f"sto-call-{ticker}-{strike}",
        date=date(2026, 1, 15),
        account="schwab/personal",
        ticker=ticker,
        action="Sell",
        quantity=1,
        proceeds=proceeds,
        cost_basis=None,
        option_details=OptionDetails(strike=strike, expiry=expiry, call_put="C"),
        basis_source="option_short_open",
    )


def test_covered_call_failing_qcc_emits_group():
    # Stock at 180 (per cost_basis 18000 / 100 shares). Short call deep ITM
    # at strike 150 with 60 DTE → fails QCC (ITM, short-dated, no cushion).
    stock_buy = Trade(
        id="stk-1",
        date=date(2026, 1, 3),
        account="schwab/personal",
        ticker="AAPL",
        action="Buy",
        quantity=100,
        proceeds=None,
        cost_basis=18000.0,
        option_details=None,
    )
    sto = _short_call_sto(strike=150.0, expiry=date(2026, 3, 20), proceeds=3500.0)
    lots = [Lot.from_trade(stock_buy)]  # short calls do not produce lots

    groups = detect_offsetting_groups(
        trades=[stock_buy, sto],
        lots=lots,
        underlying_prices={"AAPL": Decimal("180")},
    )
    cc_groups = [g for g in groups if g.kind == "covered_call"]
    assert len(cc_groups) == 1
    g = cc_groups[0]
    assert {p.kind for p in g.positions} == {"long_stock", "short_call"}
    assert "QCC" in g.reasoning or "qualified" in g.reasoning.lower()


def test_covered_call_passing_qcc_does_not_emit_group():
    # Stock at 180. Short call OTM at 200 with 180 DTE → passes QCC → no group.
    stock_buy = Trade(
        id="stk-1",
        date=date(2026, 1, 3),
        account="schwab/personal",
        ticker="AAPL",
        action="Buy",
        quantity=100,
        proceeds=None,
        cost_basis=18000.0,
        option_details=None,
    )
    sto = _short_call_sto(strike=200.0, expiry=date(2026, 7, 14), proceeds=400.0)
    lots = [Lot.from_trade(stock_buy)]

    groups = detect_offsetting_groups(
        trades=[stock_buy, sto],
        lots=lots,
        underlying_prices={"AAPL": Decimal("180")},
    )
    assert [g for g in groups if g.kind == "covered_call"] == []


def test_covered_call_without_underlying_price_falls_back_to_strike_only():
    # When no underlying price is supplied (e.g. price cache miss) the detector
    # cannot run the QCC test; it conservatively emits a covered_call group with
    # a "QCC test skipped" reasoning so the user is at least warned.
    stock_buy = Trade(
        id="stk-1",
        date=date(2026, 1, 3),
        account="schwab/personal",
        ticker="AAPL",
        action="Buy",
        quantity=100,
        proceeds=None,
        cost_basis=18000.0,
        option_details=None,
    )
    sto = _short_call_sto(strike=200.0, expiry=date(2026, 3, 20), proceeds=400.0)
    lots = [Lot.from_trade(stock_buy)]

    groups = detect_offsetting_groups(
        trades=[stock_buy, sto],
        lots=lots,
        underlying_prices=None,
    )
    cc_groups = [g for g in groups if g.kind == "covered_call"]
    assert len(cc_groups) == 1
    assert "QCC" in cc_groups[0].reasoning and "skipped" in cc_groups[0].reasoning.lower()


def test_long_call_short_call_same_expiry_emits_vertical_spread():
    long_call = _long_call_trade(strike=180.0, expiry=date(2026, 6, 19))
    sto_call = _short_call_sto(strike=200.0, expiry=date(2026, 6, 19), proceeds=200.0)
    lots = [Lot.from_trade(long_call)]

    groups = detect_offsetting_groups(trades=[long_call, sto_call], lots=lots)
    spreads = [g for g in groups if g.kind == "vertical_spread"]
    assert len(spreads) == 1
    assert {p.kind for p in spreads[0].positions} == {"long_call", "short_call"}
    assert spreads[0].rule_citation.startswith("IRC §1092")


def test_long_call_short_call_different_expiry_no_spread():
    long_call = _long_call_trade(strike=180.0, expiry=date(2026, 6, 19))
    sto_call = _short_call_sto(strike=200.0, expiry=date(2026, 9, 18), proceeds=200.0)
    lots = [Lot.from_trade(long_call)]

    groups = detect_offsetting_groups(trades=[long_call, sto_call], lots=lots)
    assert [g for g in groups if g.kind == "vertical_spread"] == []
