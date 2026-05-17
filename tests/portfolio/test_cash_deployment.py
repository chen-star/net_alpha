import datetime as dt
from decimal import Decimal

from net_alpha.models.domain import CashEvent, OptionDetails, Trade
from net_alpha.portfolio.cash_flow import build_cash_deployment_series
from net_alpha.portfolio.models import AccountValuePoint


def _ev(d, kind, amount, account="Schwab/x"):
    return CashEvent(
        account=account,
        event_date=d,
        kind=kind,
        amount=amount,
        ticker=None,
        description="x",
    )


def _buy(d, basis, account="Schwab/x", ticker="SPY"):
    return Trade(
        id=f"buy-{d.isoformat()}",
        account=account,
        date=d,
        ticker=ticker,
        action="Buy",
        quantity=10.0,
        proceeds=None,
        cost_basis=basis,
        gross_cash_impact=-basis,
        option_details=None,
    )


def _avp(d, contribs, cash, holdings):
    return AccountValuePoint(
        on=d,
        contributions=Decimal(str(contribs)),
        holdings_value=Decimal(str(holdings)) if holdings is not None else None,
        cash_balance=Decimal(str(cash)),
        account_value=((Decimal(str(cash)) + Decimal(str(holdings))) if holdings is not None else None),
        net_pl=None,
    )


def test_empty_inputs_yield_empty_series():
    pts = build_cash_deployment_series(
        account_points=[],
        trades=[],
        events=[],
        accounts=None,
        with_pledged=True,
    )
    assert pts == []


def test_pre_csp_era_pledged_is_zero():
    avps = [
        _avp(dt.date(2026, 1, 5), 1000, 1000, 0),
        _avp(dt.date(2026, 1, 10), 1000, 400, 600),
    ]
    trades = [_buy(dt.date(2026, 1, 10), 600)]
    pts = build_cash_deployment_series(
        account_points=avps,
        trades=trades,
        events=[_ev(dt.date(2026, 1, 5), "transfer_in", 1000.0)],
        accounts=None,
        with_pledged=True,
    )
    assert len(pts) == 2
    assert all(p.pledged == Decimal("0") for p in pts)
    assert pts[0].free_cash == Decimal("1000") and pts[0].invested == Decimal("0")
    assert pts[1].free_cash == Decimal("400") and pts[1].invested == Decimal("600")


def test_csp_open_ramps_pledged_close_drops_it():
    avps = [
        _avp(dt.date(2026, 4, 1), 40_000, 40_000, 0),
        _avp(dt.date(2026, 4, 10), 40_000, 40_100, 0),
        _avp(dt.date(2026, 4, 20), 40_000, 40_050, 0),
    ]
    sto = Trade(
        id="sto",
        account="Schwab/x",
        date=dt.date(2026, 4, 10),
        ticker="SPY 2026-06-20 P400",
        action="Sell",
        quantity=1.0,
        proceeds=100.0,
        cost_basis=None,
        gross_cash_impact=100.0,
        option_details=OptionDetails(strike=400.0, expiry=dt.date(2026, 6, 20), call_put="P"),
    )
    btc = Trade(
        id="btc",
        account="Schwab/x",
        date=dt.date(2026, 4, 20),
        ticker="SPY 2026-06-20 P400",
        action="Buy",
        quantity=1.0,
        proceeds=None,
        cost_basis=50.0,
        gross_cash_impact=-50.0,
        option_details=OptionDetails(strike=400.0, expiry=dt.date(2026, 6, 20), call_put="P"),
    )
    pts = build_cash_deployment_series(
        account_points=avps,
        trades=[sto, btc],
        events=[_ev(dt.date(2026, 4, 1), "transfer_in", 40_000.0)],
        accounts=None,
        with_pledged=True,
    )
    assert pts[0].pledged == Decimal("0")
    assert pts[1].pledged == Decimal("40000.00")
    assert pts[1].free_cash == Decimal("100")
    assert pts[2].pledged == Decimal("0")
    assert pts[2].free_cash == Decimal("40050")


def test_with_pledged_false_returns_none_for_pledged_field():
    avps = [_avp(dt.date(2026, 1, 5), 1000, 1000, 0)]
    pts = build_cash_deployment_series(
        account_points=avps,
        trades=[],
        events=[_ev(dt.date(2026, 1, 5), "transfer_in", 1000.0)],
        accounts=None,
        with_pledged=False,
    )
    assert pts[0].pledged is None
    assert pts[0].free_cash == Decimal("1000")
    assert pts[0].invested == Decimal("0")


def test_unpriced_holdings_yields_none_invested():
    avps = [_avp(dt.date(2026, 1, 5), 1000, 1000, None)]
    pts = build_cash_deployment_series(
        account_points=avps,
        trades=[],
        events=[_ev(dt.date(2026, 1, 5), "transfer_in", 1000.0)],
        accounts=None,
        with_pledged=True,
    )
    assert pts[0].invested is None
    assert pts[0].free_cash == Decimal("1000")
    assert pts[0].pledged == Decimal("0")


def test_pledged_clamps_to_cash_balance_when_collateral_exceeds_cash():
    """The pledged-cash compute is naive about cash drawdowns: it sums
    strike × 100 × qty for open short puts regardless of whether the
    account still holds that much cash. After a market draw, cash can dip
    below the notional collateral. The series clamps pledged to cash so
    free_cash never goes negative and the stack arithmetic stays sane
    (free + pledged + invested = total)."""
    # CSP on a $400 strike → $40k collateral. Account holds $5k cash —
    # below the notional. The clamp pins pledged = $5k, free = $0.
    avps = [_avp(dt.date(2026, 4, 10), 40_000, 5_000, 0)]
    sto = Trade(
        id="sto",
        account="Schwab/x",
        date=dt.date(2026, 4, 10),
        ticker="SPY 2026-06-20 P400",
        action="Sell",
        quantity=1.0,
        proceeds=100.0,
        cost_basis=None,
        gross_cash_impact=100.0,
        option_details=OptionDetails(
            strike=400.0,
            expiry=dt.date(2026, 6, 20),
            call_put="P",
        ),
    )
    pts = build_cash_deployment_series(
        account_points=avps,
        trades=[sto],
        events=[_ev(dt.date(2026, 4, 1), "transfer_in", 5_000.0)],
        accounts=None,
        with_pledged=True,
    )
    assert pts[0].pledged == Decimal("5000.00")
    assert pts[0].free_cash == Decimal("0.00")
