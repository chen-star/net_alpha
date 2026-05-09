from datetime import date

import pytest

from net_alpha.brokers.robinhood import RobinhoodParser


def _row(**kw):
    base = {
        "Activity Date": "",
        "Process Date": "",
        "Settle Date": "",
        "Instrument": "",
        "Description": "",
        "Trans Code": "",
        "Quantity": "",
        "Price": "",
        "Amount": "",
    }
    base.update(kw)
    return base


def _parse(rows):
    return RobinhoodParser().parse(rows, "robinhood/personal")


def test_parses_simple_buy():
    rows = [
        _row(
            **{
                "Activity Date": "10/15/2024",
                "Instrument": "TSLA",
                "Trans Code": "Buy",
                "Quantity": "10",
                "Price": "240.00",
                "Amount": "-2400.00",
            }
        )
    ]
    trades = _parse(rows)
    assert len(trades) == 1
    assert trades[0].action == "Buy"
    assert trades[0].ticker == "TSLA"
    assert trades[0].quantity == 10.0
    assert trades[0].cost_basis == 2400.0
    assert trades[0].date == date(2024, 10, 15)


def test_parses_simple_sell():
    rows = [
        _row(
            **{
                "Activity Date": "10/20/2024",
                "Instrument": "TSLA",
                "Trans Code": "Sell",
                "Quantity": "10",
                "Price": "200.00",
                "Amount": "2000.00",
            }
        )
    ]
    trades = _parse(rows)
    assert len(trades) == 1
    assert trades[0].action == "Sell"
    assert trades[0].proceeds == 2000.0
    assert trades[0].cost_basis is None


def test_invalid_date_raises_with_row_number():
    rows = [
        _row(
            **{
                "Activity Date": "13/40/9999",
                "Instrument": "TSLA",
                "Trans Code": "Buy",
                "Quantity": "1",
                "Price": "1",
                "Amount": "-1.00",
            }
        )
    ]
    with pytest.raises(ValueError, match="Row 1"):
        _parse(rows)


def test_bto_parses_as_buy_with_option_details():
    rows = [
        _row(
            **{
                "Activity Date": "10/25/2024",
                "Instrument": "TSLA $250 Call 12/20/2024",
                "Trans Code": "BTO",
                "Quantity": "1",
                "Price": "5.00",
                "Amount": "-500.00",
            }
        )
    ]
    trades = _parse(rows)
    assert len(trades) == 1
    assert trades[0].action == "Buy"
    assert trades[0].ticker == "TSLA"
    assert trades[0].cost_basis == 500.0
    assert trades[0].option_details is not None
    assert trades[0].option_details.strike == 250.0
    assert trades[0].option_details.call_put == "C"
    assert trades[0].option_details.expiry == date(2024, 12, 20)
    assert trades[0].basis_source == "unknown"


def test_stc_parses_as_sell_with_option_details():
    rows = [
        _row(
            **{
                "Activity Date": "11/01/2024",
                "Instrument": "TSLA $250 Call 12/20/2024",
                "Trans Code": "STC",
                "Quantity": "1",
                "Price": "8.00",
                "Amount": "800.00",
            }
        )
    ]
    trades = _parse(rows)
    assert len(trades) == 1
    assert trades[0].action == "Sell"
    assert trades[0].proceeds == 800.0
    assert trades[0].option_details is not None
    assert trades[0].basis_source == "unknown"


def test_sto_parses_as_sell_with_short_open_marker():
    rows = [
        _row(
            **{
                "Activity Date": "10/25/2024",
                "Instrument": "TSLA $250 Put 12/20/2024",
                "Trans Code": "STO",
                "Quantity": "1",
                "Price": "3.00",
                "Amount": "300.00",
            }
        )
    ]
    trades = _parse(rows)
    assert len(trades) == 1
    assert trades[0].action == "Sell"
    assert trades[0].proceeds == 300.0
    assert trades[0].basis_source == "option_short_open"


def test_btc_parses_as_buy_with_short_close_marker():
    rows = [
        _row(
            **{
                "Activity Date": "11/01/2024",
                "Instrument": "TSLA $250 Put 12/20/2024",
                "Trans Code": "BTC",
                "Quantity": "1",
                "Price": "1.00",
                "Amount": "-100.00",
            }
        )
    ]
    trades = _parse(rows)
    assert len(trades) == 1
    assert trades[0].action == "Buy"
    assert trades[0].cost_basis == 100.0
    assert trades[0].basis_source == "option_short_close"


def test_oexp_emits_no_trade():
    rows = [
        _row(
            **{
                "Activity Date": "12/20/2024",
                "Instrument": "TSLA $300 Call 12/20/2024",
                "Trans Code": "OEXP",
                "Quantity": "1",
                "Price": "0",
                "Amount": "0",
            }
        )
    ]
    trades = _parse(rows)
    assert trades == []


def test_oexp_does_not_warn():
    rows = [
        _row(
            **{
                "Activity Date": "12/20/2024",
                "Instrument": "TSLA $300 Call 12/20/2024",
                "Trans Code": "OEXP",
                "Quantity": "1",
                "Price": "0",
                "Amount": "0",
            }
        )
    ]
    result = RobinhoodParser().parse_full(rows, "robinhood/personal")
    assert result.parse_warnings == []


def test_same_day_identical_fills_get_distinct_occurrence_index():
    rows = [
        _row(
            **{
                "Activity Date": "07/29/2024",
                "Instrument": "GPRO",
                "Trans Code": "Sell",
                "Quantity": "100",
                "Price": "2.00",
                "Amount": "200.00",
            }
        ),
        _row(
            **{
                "Activity Date": "07/29/2024",
                "Instrument": "GPRO",
                "Trans Code": "Sell",
                "Quantity": "100",
                "Price": "2.00",
                "Amount": "200.00",
            }
        ),
    ]
    trades = _parse(rows)
    assert len(trades) == 2
    assert trades[0].occurrence_index == 0
    assert trades[1].occurrence_index == 1
    assert trades[0].compute_natural_key() != trades[1].compute_natural_key()


def test_oasgn_short_put_offsets_underlying_buy_basis():
    rows = [
        # Short put opened — premium received $300.
        _row(
            **{
                "Activity Date": "10/01/2024",
                "Instrument": "AAPL $150 Put 11/15/2024",
                "Trans Code": "STO",
                "Quantity": "1",
                "Price": "3.00",
                "Amount": "300.00",
            }
        ),
        # Assigned: option leg (no trade emitted, premium folded via pre-pass).
        _row(
            **{
                "Activity Date": "11/15/2024",
                "Instrument": "AAPL $150 Put 11/15/2024",
                "Trans Code": "OASGN",
                "Quantity": "1",
                "Price": "0",
                "Amount": "0",
            }
        ),
        # Underlying buy at strike on assignment date — Robinhood Path A.
        _row(
            **{
                "Activity Date": "11/15/2024",
                "Instrument": "AAPL",
                "Trans Code": "Buy",
                "Quantity": "100",
                "Price": "150.00",
                "Amount": "-15000.00",
            }
        ),
    ]
    trades = _parse(rows)
    underlying = [t for t in trades if t.ticker == "AAPL" and t.option_details is None]
    assert len(underlying) == 1
    # 15000 (strike × 100) − 300 (premium) = 14700.
    assert underlying[0].cost_basis == 14700.0
    assert underlying[0].basis_source == "put_assignment"


def test_oasgn_does_not_emit_a_trade_for_the_option_leg():
    rows = [
        _row(
            **{
                "Activity Date": "10/01/2024",
                "Instrument": "AAPL $150 Put 11/15/2024",
                "Trans Code": "STO",
                "Quantity": "1",
                "Price": "3.00",
                "Amount": "300.00",
            }
        ),
        _row(
            **{
                "Activity Date": "11/15/2024",
                "Instrument": "AAPL $150 Put 11/15/2024",
                "Trans Code": "OASGN",
                "Quantity": "1",
                "Price": "0",
                "Amount": "0",
            }
        ),
        _row(
            **{
                "Activity Date": "11/15/2024",
                "Instrument": "AAPL",
                "Trans Code": "Buy",
                "Quantity": "100",
                "Price": "150.00",
                "Amount": "-15000.00",
            }
        ),
    ]
    trades = _parse(rows)
    # Two trades total: STO (the option Sell) + the underlying Buy. OASGN itself does not emit anything.
    assert len(trades) == 2
    option_trades = [t for t in trades if t.option_details is not None]
    assert len(option_trades) == 1  # just the STO


def test_oasgn_with_no_prior_sto_does_not_offset():
    """Defensive: an OASGN row without any prior STO leaves the underlying Buy basis untouched."""
    rows = [
        _row(
            **{
                "Activity Date": "11/15/2024",
                "Instrument": "AAPL $150 Put 11/15/2024",
                "Trans Code": "OASGN",
                "Quantity": "1",
                "Price": "0",
                "Amount": "0",
            }
        ),
        _row(
            **{
                "Activity Date": "11/15/2024",
                "Instrument": "AAPL",
                "Trans Code": "Buy",
                "Quantity": "100",
                "Price": "150.00",
                "Amount": "-15000.00",
            }
        ),
    ]
    trades = _parse(rows)
    underlying = [t for t in trades if t.ticker == "AAPL" and t.option_details is None]
    assert len(underlying) == 1
    assert underlying[0].cost_basis == 15000.0  # unchanged
    assert underlying[0].basis_source == "unknown"


def test_oasgn_call_assignment_does_not_offset_underlying():
    """Calls are out of scope for the v1 helper — only puts get basis-offset."""
    rows = [
        _row(
            **{
                "Activity Date": "10/01/2024",
                "Instrument": "AAPL $200 Call 11/15/2024",
                "Trans Code": "STO",
                "Quantity": "1",
                "Price": "5.00",
                "Amount": "500.00",
            }
        ),
        _row(
            **{
                "Activity Date": "11/15/2024",
                "Instrument": "AAPL $200 Call 11/15/2024",
                "Trans Code": "OASGN",
                "Quantity": "1",
                "Price": "0",
                "Amount": "0",
            }
        ),
        # For a sold call assignment, AAPL would be SOLD at strike (not bought). But even if
        # there were a Buy row by mistake, the helper should not touch it.
        _row(
            **{
                "Activity Date": "11/15/2024",
                "Instrument": "AAPL",
                "Trans Code": "Buy",
                "Quantity": "100",
                "Price": "200.00",
                "Amount": "-20000.00",
            }
        ),
    ]
    trades = _parse(rows)
    underlying = [t for t in trades if t.ticker == "AAPL" and t.option_details is None]
    assert len(underlying) == 1
    assert underlying[0].cost_basis == 20000.0  # call premium NOT folded in
    assert underlying[0].basis_source == "unknown"


def test_oasgn_partial_close_before_assignment_uses_net_premium():
    """STO 2 contracts at $600, BTC 1 contract at $100, 1 contract assigned.
    Net premium = (600 − 100) / 2 contracts × 1 assigned = $250 offset."""
    rows = [
        _row(
            **{
                "Activity Date": "09/01/2024",
                "Instrument": "AAPL $150 Put 11/15/2024",
                "Trans Code": "STO",
                "Quantity": "2",
                "Price": "3.00",
                "Amount": "600.00",
            }
        ),
        _row(
            **{
                "Activity Date": "10/01/2024",
                "Instrument": "AAPL $150 Put 11/15/2024",
                "Trans Code": "BTC",
                "Quantity": "1",
                "Price": "1.00",
                "Amount": "-100.00",
            }
        ),
        _row(
            **{
                "Activity Date": "11/15/2024",
                "Instrument": "AAPL $150 Put 11/15/2024",
                "Trans Code": "OASGN",
                "Quantity": "1",
                "Price": "0",
                "Amount": "0",
            }
        ),
        _row(
            **{
                "Activity Date": "11/15/2024",
                "Instrument": "AAPL",
                "Trans Code": "Buy",
                "Quantity": "100",
                "Price": "150.00",
                "Amount": "-15000.00",
            }
        ),
    ]
    trades = _parse(rows)
    underlying = [t for t in trades if t.ticker == "AAPL" and t.option_details is None]
    assert len(underlying) == 1
    # 15000 − 250 = 14750.
    assert underlying[0].cost_basis == 14750.0
    assert underlying[0].basis_source == "put_assignment"


def test_spl_emits_no_trade_and_logs_warning():
    rows = [
        _row(
            **{
                "Activity Date": "08/25/2024",
                "Instrument": "NVDA",
                "Trans Code": "SPL",
                "Quantity": "10",
                "Price": "0",
                "Amount": "0",
                "Description": "Stock Split 10:1",
            }
        )
    ]
    result = RobinhoodParser().parse_full(rows, "robinhood/personal")
    assert result.trades == []
    assert any("SPL" in w for w in result.parse_warnings)


def test_rec_share_transfer_in_marks_transfer_in_with_basis_unknown():
    rows = [
        _row(
            **{
                "Activity Date": "08/01/2024",
                "Instrument": "AAPL",
                "Trans Code": "REC",
                "Quantity": "50",
                "Price": "",
                "Amount": "",
            }
        )
    ]
    trades = _parse(rows)
    assert len(trades) == 1
    assert trades[0].action == "Buy"
    assert trades[0].quantity == 50.0
    assert trades[0].basis_source == "transfer_in"
    assert trades[0].basis_unknown is True
    assert trades[0].cost_basis is None


def test_rec_share_transfer_out_marks_transfer_out():
    rows = [
        _row(
            **{
                "Activity Date": "08/01/2024",
                "Instrument": "AAPL",
                "Trans Code": "REC",
                "Quantity": "-50",
                "Price": "",
                "Amount": "",
            }
        )
    ]
    trades = _parse(rows)
    assert len(trades) == 1
    assert trades[0].action == "Sell"
    assert trades[0].quantity == 50.0
    assert trades[0].basis_source == "transfer_out"


def test_rec_zero_quantity_is_skipped():
    rows = [
        _row(
            **{
                "Activity Date": "08/01/2024",
                "Instrument": "AAPL",
                "Trans Code": "REC",
                "Quantity": "0",
                "Price": "",
                "Amount": "",
            }
        )
    ]
    trades = _parse(rows)
    assert trades == []


def test_crypto_buy_is_skipped_with_warning():
    rows = [
        _row(
            **{
                "Activity Date": "10/15/2024",
                "Instrument": "BTC",
                "Trans Code": "Buy",
                "Quantity": "0.001",
                "Price": "60000",
                "Amount": "-60.00",
            }
        )
    ]
    result = RobinhoodParser().parse_full(rows, "robinhood/personal")
    assert result.trades == []
    assert any("BTC" in w and "crypto" in w.lower() for w in result.parse_warnings)


def test_crypto_sell_is_skipped():
    rows = [
        _row(
            **{
                "Activity Date": "10/15/2024",
                "Instrument": "ETH",
                "Trans Code": "Sell",
                "Quantity": "0.5",
                "Price": "3000",
                "Amount": "1500.00",
            }
        )
    ]
    result = RobinhoodParser().parse_full(rows, "robinhood/personal")
    assert result.trades == []
    assert any("ETH" in w for w in result.parse_warnings)


def test_unknown_trans_code_emits_warning_and_no_trade():
    rows = [
        _row(
            **{
                "Activity Date": "10/15/2024",
                "Instrument": "AAPL",
                "Trans Code": "XYZQ",
                "Quantity": "1",
                "Price": "100",
                "Amount": "100.00",
            }
        )
    ]
    result = RobinhoodParser().parse_full(rows, "robinhood/personal")
    assert result.trades == []
    assert any("XYZQ" in w for w in result.parse_warnings)


def test_oexp_still_does_not_warn_after_unknown_warning_added():
    """Regression guard: OEXP should remain in _NON_TRADE_KNOWN_CODES so it
    doesn't fall into the unknown-warning path."""
    rows = [
        _row(
            **{
                "Activity Date": "12/20/2024",
                "Instrument": "TSLA $300 Call 12/20/2024",
                "Trans Code": "OEXP",
                "Quantity": "1",
                "Price": "0",
                "Amount": "0",
            }
        )
    ]
    result = RobinhoodParser().parse_full(rows, "robinhood/personal")
    assert result.trades == []
    assert result.parse_warnings == []
