from datetime import date
from decimal import Decimal

from net_alpha.inbox.models import Severity, SignalType
from net_alpha.inbox.signals.option_expiry import compute_option_expiry
from net_alpha.models.domain import OptionDetails
from tests.inbox.conftest import make_lot, make_prices_stub, make_repo


def _opt(*, lid: str, ticker: str, strike: float, expiry: date, call_put: str, qty: float):
    """Helper: an open option Lot. Negative qty indicates a short position."""
    return make_lot(
        lid=lid,
        trade_id=f"t-{lid}",
        ticker=ticker,
        quantity=qty,
        cost_basis=100.0,
        option=OptionDetails(strike=strike, expiry=expiry, call_put=call_put),
    )


def test_long_option_expiring_today_emits_urgent_only():
    today = date(2026, 5, 1)
    repo = make_repo(lots=[_opt(lid="1", ticker="AAPL", strike=200, expiry=today, call_put="C", qty=1)])
    prices = make_prices_stub({"AAPL": Decimal("210")})
    items = compute_option_expiry(repo=repo, prices=prices, today=today)
    types = [i.signal_type for i in items]
    assert types == [SignalType.OPTION_EXPIRY]  # long → no assignment risk
    assert items[0].severity is Severity.URGENT
    assert items[0].days_until == 0


def test_long_option_expiring_in_7_days_is_watch():
    today = date(2026, 5, 1)
    expiry = date(2026, 5, 8)
    repo = make_repo(lots=[_opt(lid="1", ticker="AAPL", strike=200, expiry=expiry, call_put="C", qty=1)])
    prices = make_prices_stub({"AAPL": Decimal("210")})
    items = compute_option_expiry(repo=repo, prices=prices, today=today)
    expiry_items = [i for i in items if i.signal_type is SignalType.OPTION_EXPIRY]
    assert len(expiry_items) == 1
    assert expiry_items[0].severity is Severity.WATCH


def test_long_option_expiring_in_15_days_excluded():
    today = date(2026, 5, 1)
    expiry = date(2026, 5, 16)
    repo = make_repo(lots=[_opt(lid="1", ticker="AAPL", strike=200, expiry=expiry, call_put="C", qty=1)])
    prices = make_prices_stub({"AAPL": Decimal("210")})
    items = compute_option_expiry(repo=repo, prices=prices, today=today)
    assert items == []


def test_expired_yesterday_excluded():
    today = date(2026, 5, 1)
    expiry = date(2026, 4, 30)
    repo = make_repo(lots=[_opt(lid="1", ticker="AAPL", strike=200, expiry=expiry, call_put="C", qty=1)])
    prices = make_prices_stub({"AAPL": Decimal("210")})
    items = compute_option_expiry(repo=repo, prices=prices, today=today)
    assert items == []


def test_short_call_itm_within_7d_emits_assignment_risk():
    today = date(2026, 5, 1)
    expiry = date(2026, 5, 5)  # 4 days out
    repo = make_repo(lots=[_opt(lid="9", ticker="AAPL", strike=200, expiry=expiry, call_put="C", qty=-1)])
    prices = make_prices_stub({"AAPL": Decimal("210")})  # $10 ITM
    items = compute_option_expiry(repo=repo, prices=prices, today=today)
    types_by = {i.signal_type for i in items}
    assert SignalType.OPTION_EXPIRY in types_by
    assert SignalType.ASSIGNMENT_RISK in types_by
    risk = next(i for i in items if i.signal_type is SignalType.ASSIGNMENT_RISK)
    assert risk.severity is Severity.URGENT
    assert risk.dismiss_key == "assignment_risk:t-9"
    # 1 contract * 100 multiplier * $10 ITM = $1000
    assert risk.dollar_impact == Decimal("1000")
    assert "ITM" in risk.subtitle


def test_short_call_otm_no_assignment_risk():
    today = date(2026, 5, 1)
    expiry = date(2026, 5, 5)
    repo = make_repo(lots=[_opt(lid="9", ticker="AAPL", strike=200, expiry=expiry, call_put="C", qty=-1)])
    prices = make_prices_stub({"AAPL": Decimal("190")})  # OTM for short call
    items = compute_option_expiry(repo=repo, prices=prices, today=today)
    risk_items = [i for i in items if i.signal_type is SignalType.ASSIGNMENT_RISK]
    assert risk_items == []


def test_short_put_itm_emits_assignment_risk():
    today = date(2026, 5, 1)
    expiry = date(2026, 5, 5)
    repo = make_repo(lots=[_opt(lid="9", ticker="AAPL", strike=200, expiry=expiry, call_put="P", qty=-1)])
    prices = make_prices_stub({"AAPL": Decimal("190")})  # $10 ITM for short put
    items = compute_option_expiry(repo=repo, prices=prices, today=today)
    risk = [i for i in items if i.signal_type is SignalType.ASSIGNMENT_RISK]
    assert len(risk) == 1
    assert risk[0].dollar_impact == Decimal("1000")


def test_short_at_strike_is_itm():
    """Boundary: strike == underlying counts as ITM (>= for calls, <= for puts)."""
    today = date(2026, 5, 1)
    expiry = date(2026, 5, 5)
    repo = make_repo(lots=[_opt(lid="9", ticker="AAPL", strike=200, expiry=expiry, call_put="C", qty=-1)])
    prices = make_prices_stub({"AAPL": Decimal("200")})
    items = compute_option_expiry(repo=repo, prices=prices, today=today)
    assert any(i.signal_type is SignalType.ASSIGNMENT_RISK for i in items)


def test_short_no_underlying_quote_skips_assignment_risk():
    today = date(2026, 5, 1)
    expiry = date(2026, 5, 5)
    repo = make_repo(lots=[_opt(lid="9", ticker="AAPL", strike=200, expiry=expiry, call_put="C", qty=-1)])
    prices = make_prices_stub({})  # no quote at all
    items = compute_option_expiry(repo=repo, prices=prices, today=today)
    risk_items = [i for i in items if i.signal_type is SignalType.ASSIGNMENT_RISK]
    assert risk_items == []


def test_assignment_risk_window_boundary():
    """8 days to expiry → expiry signal yes, assignment risk no."""
    today = date(2026, 5, 1)
    expiry = date(2026, 5, 9)  # 8 days
    repo = make_repo(lots=[_opt(lid="9", ticker="AAPL", strike=200, expiry=expiry, call_put="C", qty=-1)])
    prices = make_prices_stub({"AAPL": Decimal("210")})
    items = compute_option_expiry(repo=repo, prices=prices, today=today)
    types_by = {i.signal_type for i in items}
    assert SignalType.OPTION_EXPIRY in types_by
    assert SignalType.ASSIGNMENT_RISK not in types_by


def test_long_itm_call_no_assignment_risk():
    today = date(2026, 5, 1)
    expiry = date(2026, 5, 5)
    repo = make_repo(lots=[_opt(lid="9", ticker="AAPL", strike=200, expiry=expiry, call_put="C", qty=1)])
    prices = make_prices_stub({"AAPL": Decimal("210")})
    items = compute_option_expiry(repo=repo, prices=prices, today=today)
    assert all(i.signal_type is not SignalType.ASSIGNMENT_RISK for i in items)
