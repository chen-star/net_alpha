import datetime as dt
from decimal import Decimal

from net_alpha.models.domain import CashEvent, Trade
from net_alpha.portfolio.cash_flow import build_cash_balance_series


def _ev(d, kind, amount, account="Schwab/x", description="x"):
    return CashEvent(account=account, event_date=d, kind=kind,
                     amount=amount, ticker=None, description=description)


def _trade(d, action, gross, account="Schwab/x", ticker="SPIR"):
    return Trade(
        id="t", account=account, date=d, ticker=ticker,
        action=action, quantity=10.0,
        proceeds=gross if action == "Sell" else None,
        cost_basis=abs(gross) if action == "Buy" else None,
        gross_cash_impact=gross,
        option_details=None,
    )


def test_empty_inputs_yield_empty_series():
    pts = build_cash_balance_series(events=[], trades=[], account=None, period=None)
    assert pts == []


def test_single_deposit_jumps_balance_and_contributions():
    events = [_ev(dt.date(2026, 3, 4), "transfer_in", 300.0, description="DEPOSIT")]
    pts = build_cash_balance_series(events=events, trades=[], account=None, period=None)
    assert len(pts) == 1
    assert pts[0].cash_balance == Decimal("300")
    assert pts[0].cumulative_contributions == Decimal("300")


def test_buy_decreases_balance_but_not_contributions():
    events = [_ev(dt.date(2026, 3, 4), "transfer_in", 300.0)]
    trades = [_trade(dt.date(2026, 3, 5), "Buy", -158.80)]
    pts = build_cash_balance_series(events=events, trades=trades, account=None, period=None)
    assert pts[-1].cash_balance == Decimal("141.20")
    assert pts[-1].cumulative_contributions == Decimal("300")


def test_sweep_out_then_in_dips_and_recovers():
    events = [
        _ev(dt.date(2026, 4, 22), "sweep_out", 4460.97, description="Sweep to Futures"),
        _ev(dt.date(2026, 4, 24), "sweep_in",  307.00, description="Sweep from Futures"),
    ]
    pts = build_cash_balance_series(events=events, trades=[], account=None, period=None)
    assert pts[0].cash_balance == Decimal("-4460.97")
    assert pts[1].cash_balance == Decimal("-4153.97")


def test_dividend_does_not_change_contributions():
    events = [
        _ev(dt.date(2026, 3, 4), "transfer_in", 100.0),
        _ev(dt.date(2026, 3, 31), "dividend", 4.47, description="SQQQ"),
    ]
    pts = build_cash_balance_series(events=events, trades=[], account=None, period=None)
    assert pts[-1].cash_balance == Decimal("104.47")
    assert pts[-1].cumulative_contributions == Decimal("100")


def test_account_filter_excludes_other_accounts():
    events = [
        _ev(dt.date(2026, 3, 4), "transfer_in", 100.0, account="Schwab/A"),
        _ev(dt.date(2026, 3, 4), "transfer_in", 999.0, account="Schwab/B"),
    ]
    pts = build_cash_balance_series(events=events, trades=[], account="Schwab/A", period=None)
    assert pts[-1].cash_balance == Decimal("100")


def test_period_clip_excludes_events_after_window():
    events = [
        _ev(dt.date(2025, 12, 31), "transfer_in", 1000.0),
        _ev(dt.date(2026, 6, 1),  "transfer_in", 200.0),
    ]
    # period = (2026, 2027) means YTD 2026
    pts = build_cash_balance_series(events=events, trades=[], account=None, period=(2026, 2027))
    # The 2025 event sets the opening balance carried into 2026.
    # The 2026 event makes the balance jump.
    assert pts[-1].cash_balance == Decimal("1200")
    assert pts[-1].cumulative_contributions == Decimal("1200")


def test_put_assignment_uses_gross_not_cost_basis():
    """A buy with cost_basis adjusted-down for put_assignment must still
    debit cash by the gross strike × qty amount."""
    trades = [_trade(dt.date(2026, 4, 17), "Buy", -300.0)]
    # Override cost_basis to 213 (basis-adjusted for premium); gross stays -300.
    trades[0].cost_basis = 213.0
    pts = build_cash_balance_series(events=[], trades=trades, account=None, period=None)
    assert pts[-1].cash_balance == Decimal("-300")


def test_legacy_trade_without_gross_falls_back_to_proceeds_or_cost_basis():
    trades = [_trade(dt.date(2026, 1, 5), "Sell", 824.96)]
    trades[0].gross_cash_impact = None  # simulate pre-migration row
    pts = build_cash_balance_series(events=[], trades=trades, account=None, period=None)
    assert pts[-1].cash_balance == Decimal("824.96")


# Tests for compute_cash_kpis
from net_alpha.portfolio.cash_flow import compute_cash_kpis


def test_kpis_zero_inputs():
    kpi = compute_cash_kpis(
        events=[], trades=[], holdings_value=Decimal("0"),
        account=None, period=None,
    )
    assert kpi.cash_balance == Decimal("0")
    assert kpi.account_value == Decimal("0")
    assert kpi.growth == Decimal("0")
    assert kpi.growth_pct is None
    assert kpi.cash_share_pct == Decimal("0")


def test_kpis_simple_deposit_and_holdings():
    events = [_ev(dt.date(2026, 3, 4), "transfer_in", 1000.0)]
    kpi = compute_cash_kpis(
        events=events, trades=[], holdings_value=Decimal("250"),
        account=None, period=None,
    )
    # cash 1000 + holdings 250 = 1250 account_value, contrib 1000 → growth 250
    assert kpi.cash_balance == Decimal("1000")
    assert kpi.holdings_value == Decimal("250")
    assert kpi.account_value == Decimal("1250")
    assert kpi.net_contributions == Decimal("1000")
    assert kpi.growth == Decimal("250")
    assert kpi.growth_pct == Decimal("0.25")
    assert kpi.cash_share_pct == Decimal("0.8")  # 1000/1250


def test_kpis_growth_pct_none_when_no_contributions():
    events = [_ev(dt.date(2026, 3, 4), "dividend", 4.47)]
    kpi = compute_cash_kpis(
        events=events, trades=[], holdings_value=Decimal("0"),
        account=None, period=None,
    )
    assert kpi.net_contributions == Decimal("0")
    assert kpi.growth_pct is None


# Tests for cash_allocation_slice
from net_alpha.portfolio.cash_flow import cash_allocation_slice


def test_cash_allocation_slice_returns_current_balance():
    events = [_ev(dt.date(2026, 3, 4), "transfer_in", 100.0)]
    trades = [_trade(dt.date(2026, 3, 5), "Buy", -25.0)]
    sl = cash_allocation_slice(events=events, trades=trades, account=None)
    assert sl == Decimal("75")
