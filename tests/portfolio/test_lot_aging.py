import datetime as dt

from net_alpha.models.domain import Lot
from net_alpha.portfolio.lot_aging import top_lots_crossing_ltcg


def _lot(symbol, account, days_old, qty=10):
    today = dt.date.today()
    return Lot(
        id="l", trade_id="t", account=account,
        date=today - dt.timedelta(days=days_old),
        ticker=symbol, quantity=float(qty),
        cost_basis=1000.0, adjusted_basis=1000.0, option_details=None,
    )


def test_returns_empty_when_no_lots_within_window():
    assert top_lots_crossing_ltcg(lots=[_lot("SPY", "Tax", 10)], horizon_days=90, top_n=5) == []


def test_includes_only_lots_within_horizon():
    lots = [
        _lot("NVDA", "IRA", 357),  # 8 days to 1y
        _lot("AMD", "Tax", 344),    # 21 days
        _lot("FOO", "Tax", 200),    # >90 days away
    ]
    out = top_lots_crossing_ltcg(lots=lots, horizon_days=90, top_n=5)
    assert [lot.symbol for lot in out] == ["NVDA", "AMD"]


def test_excludes_already_long_term_lots():
    lots = [_lot("OLD", "Tax", 400)]
    assert top_lots_crossing_ltcg(lots=lots, horizon_days=90, top_n=5) == []


def test_caps_to_top_n_by_urgency():
    lots = [_lot(f"S{i}", "Tax", 365 - (1 + i)) for i in range(8)]  # 1d..8d to LTCG
    out = top_lots_crossing_ltcg(lots=lots, horizon_days=90, top_n=3)
    assert len(out) == 3
    # Most urgent first
    assert out[0].days_to_ltcg < out[-1].days_to_ltcg
