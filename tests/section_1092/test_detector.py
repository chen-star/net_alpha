from datetime import date

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
