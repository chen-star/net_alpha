from datetime import date

from net_alpha.brokers.schwab import SchwabParser


def _row(**kw):
    base = {
        "Date": "",
        "Action": "",
        "Symbol": "",
        "Description": "",
        "Quantity": "",
        "Price": "",
        "Fees & Comm": "",
        "Amount": "",
    }
    base.update(kw)
    return base


def _parse(rows):
    return SchwabParser().parse_full(rows, "Schwab/short_term")


def test_moneylink_transfer_in_emits_transfer_in():
    rows = [_row(Date="03/04/2026", Action="MoneyLink Transfer", Description="Tfr WELLS FARGO", Amount="$300.00")]
    res = _parse(rows)
    assert len(res.cash_events) == 1
    e = res.cash_events[0]
    assert e.kind == "transfer_in"
    assert e.amount == 300.0
    assert e.event_date == date(2026, 3, 4)
    assert e.description == "Tfr WELLS FARGO"


def test_moneylink_transfer_out_emits_transfer_out():
    rows = [_row(Date="03/04/2026", Action="MoneyLink Transfer", Description="Tfr OUT", Amount="-$200.00")]
    res = _parse(rows)
    assert res.cash_events[0].kind == "transfer_out"
    assert res.cash_events[0].amount == 200.0


def test_qualified_dividend_emits_dividend_with_ticker():
    rows = [
        _row(Date="03/31/2026", Action="Qualified Dividend", Symbol="VST", Description="VISTRA CORP", Amount="$0.23")
    ]
    res = _parse(rows)
    e = res.cash_events[0]
    assert e.kind == "dividend"
    assert e.amount == 0.23
    assert e.ticker == "VST"


def test_non_qualified_dividend_emits_dividend():
    rows = [
        _row(
            Date="03/31/2026",
            Action="Non-Qualified Div",
            Symbol="SQQQ",
            Description="PROSHARES SHORT QQQ",
            Amount="$4.47",
        )
    ]
    res = _parse(rows)
    assert res.cash_events[0].kind == "dividend"
    assert res.cash_events[0].ticker == "SQQQ"


def test_pr_yr_non_qual_div_emits_dividend():
    rows = [
        _row(Date="03/31/2026", Action="Pr Yr Non-Qual Div", Symbol="ABC", Description="PRIOR YEAR DIV", Amount="$1.50")
    ]
    res = _parse(rows)
    assert res.cash_events[0].kind == "dividend"


def test_cash_dividend_emits_dividend():
    rows = [_row(Date="03/31/2026", Action="Cash Dividend", Symbol="XYZ", Description="DIV", Amount="$2.00")]
    res = _parse(rows)
    assert res.cash_events[0].kind == "dividend"


def test_cash_in_lieu_emits_dividend():
    rows = [_row(Date="03/15/2026", Action="Cash In Lieu", Symbol="ABC", Description="FRACTIONAL", Amount="$0.42")]
    res = _parse(rows)
    assert res.cash_events[0].kind == "dividend"


def test_credit_interest_emits_interest_no_ticker():
    rows = [_row(Date="02/26/2026", Action="Credit Interest", Description="SCHWAB1 INT 01/29-02/25", Amount="$0.14")]
    res = _parse(rows)
    e = res.cash_events[0]
    assert e.kind == "interest"
    assert e.ticker is None


def test_adr_mgmt_fee_emits_fee():
    rows = [_row(Date="02/15/2026", Action="ADR Mgmt Fee", Symbol="WRD", Description="ADR FEE", Amount="-$0.50")]
    res = _parse(rows)
    e = res.cash_events[0]
    assert e.kind == "fee"
    assert e.amount == 0.50  # always positive; sign implied by kind
    assert e.ticker == "WRD"


def test_foreign_tax_paid_emits_fee():
    rows = [
        _row(Date="03/31/2026", Action="Foreign Tax Paid", Symbol="ADR", Description="FOREIGN TAX", Amount="-$1.20")
    ]
    res = _parse(rows)
    assert res.cash_events[0].kind == "fee"


def test_sweep_to_futures_emits_sweep_out():
    rows = [_row(Date="04/22/2026", Action="Futures MM Sweep", Description="Sweep to Futures", Amount="-$4460.97")]
    res = _parse(rows)
    e = res.cash_events[0]
    assert e.kind == "sweep_out"
    assert e.amount == 4460.97


def test_sweep_from_futures_emits_sweep_in():
    rows = [_row(Date="04/06/2026", Action="Futures MM Sweep", Description="Sweep from Futures", Amount="$10.76")]
    res = _parse(rows)
    assert res.cash_events[0].kind == "sweep_in"


def test_journal_emits_transfer_in_or_out_by_sign():
    rows = [
        _row(Date="04/01/2026", Action="Journal", Description="JOURNAL +", Amount="$50.00"),
        _row(Date="04/01/2026", Action="Journal", Description="JOURNAL -", Amount="-$50.00"),
    ]
    res = _parse(rows)
    kinds = sorted(e.kind for e in res.cash_events)
    assert kinds == ["transfer_in", "transfer_out"]


def test_unknown_non_trade_action_emits_warning_and_skips():
    rows = [_row(Date="04/01/2026", Action="Mystery Magic", Description="???", Amount="$1.00")]
    res = _parse(rows)
    assert res.cash_events == []
    assert any("Mystery Magic" in w for w in res.parse_warnings)


def test_trade_rows_still_produce_trades_not_cash_events():
    """Regression: Buy/Sell rows should NOT show up as cash events."""
    rows = [
        _row(
            Date="04/24/2026",
            Action="Buy",
            Symbol="SPIR",
            Description="SPIRE GLOBAL",
            Quantity="10",
            Price="$15.88",
            Amount="-$158.80",
        )
    ]
    res = _parse(rows)
    assert len(res.trades) == 1
    assert res.cash_events == []


def test_security_transfer_remains_a_trade_not_a_cash_event():
    """Journaled Shares / Security Transfer move shares, not Schwab1 cash.
    They stay in the trade-side path with basis_source=transfer_in/out.
    """
    rows = [
        _row(
            Date="04/01/2026",
            Action="Security Transfer",
            Symbol="ABC",
            Description="TRANSFER IN",
            Quantity="100",
            Amount="",
        )
    ]
    res = _parse(rows)
    assert len(res.trades) == 1
    assert res.trades[0].basis_source == "transfer_in"
    assert res.cash_events == []


def test_sell_to_open_and_buy_to_close_emit_no_warnings_no_cash_events():
    """Option-side actions consumed by put-assignment basis-offset helper
    should be silently ignored by parse_full — neither Trade nor CashEvent,
    and crucially NO 'Unknown action' warning."""
    rows = [
        _row(
            Date="03/19/2026",
            Action="Sell to Open",
            Symbol="RR 04/17/2026 3.00 P",
            Description="PUT RICHTECH ROBOTICS",
            Quantity="1",
            Price="$0.88",
            Amount="$87.34",
        ),
        _row(
            Date="04/14/2026",
            Action="Buy to Close",
            Symbol="UUUU 04/17/2026 20.00 P",
            Description="PUT ENERGY FUELS",
            Quantity="1",
            Price="$0.82",
            Amount="-$82.66",
        ),
    ]
    res = _parse(rows)
    assert res.cash_events == []
    assert res.parse_warnings == []


def test_reinvest_dividend_emits_dividend():
    rows = [
        _row(
            Date="03/31/2026",
            Action="Reinvest Dividend",
            Symbol="VTI",
            Description="REINVEST DIV",
            Amount="$12.34",
        )
    ]
    res = _parse(rows)
    assert len(res.cash_events) == 1
    assert res.cash_events[0].kind == "dividend"
    assert res.cash_events[0].amount == 12.34
    assert res.parse_warnings == []


def test_long_term_cap_gain_emits_dividend():
    rows = [
        _row(
            Date="12/15/2026",
            Action="Long Term Cap Gain",
            Symbol="VTI",
            Description="LT CAP GAIN",
            Amount="$45.67",
        )
    ]
    res = _parse(rows)
    assert res.cash_events[0].kind == "dividend"
    assert res.parse_warnings == []
