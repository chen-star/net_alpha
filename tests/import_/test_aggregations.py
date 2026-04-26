import datetime as dt

from net_alpha.import_.aggregations import compute_import_aggregates
from net_alpha.models.domain import OptionDetails, Trade


def _t(day, *, ticker="AAPL", action="Buy", opt=None):
    return Trade(
        account="schwab/tax",
        date=day,
        ticker=ticker,
        action=action,
        quantity=10.0,
        proceeds=None if action == "Buy" else 1000.0,
        cost_basis=1000.0 if action == "Buy" else None,
        option_details=opt,
    )


def _opt(strike=100.0, expiry=dt.date(2026, 6, 19), call_put="C"):
    return OptionDetails(strike=strike, expiry=expiry, call_put=call_put)


def test_empty_returns_zero_counts_and_none_dates():
    out = compute_import_aggregates(trades=[], parse_warnings=[])
    assert out.min_trade_date is None
    assert out.max_trade_date is None
    assert out.equity_count == 0
    assert out.option_count == 0
    assert out.option_expiry_count == 0
    assert out.parse_warnings == []


def test_date_range_min_and_max():
    out = compute_import_aggregates(
        trades=[
            _t(dt.date(2026, 1, 5)),
            _t(dt.date(2026, 3, 12)),
            _t(dt.date(2026, 2, 28)),
        ],
        parse_warnings=[],
    )
    assert out.min_trade_date == dt.date(2026, 1, 5)
    assert out.max_trade_date == dt.date(2026, 3, 12)


def test_equity_vs_option_split():
    trades = [
        _t(dt.date(2026, 1, 5)),  # equity
        _t(dt.date(2026, 1, 6)),  # equity
        _t(dt.date(2026, 1, 7), opt=_opt()),  # option
    ]
    out = compute_import_aggregates(trades=trades, parse_warnings=[])
    assert out.equity_count == 2
    assert out.option_count == 1
    assert out.option_expiry_count == 0


def test_parse_warnings_passed_through():
    out = compute_import_aggregates(trades=[], parse_warnings=["row 4: bad date", "row 7: skipped"])
    assert out.parse_warnings == ["row 4: bad date", "row 7: skipped"]
