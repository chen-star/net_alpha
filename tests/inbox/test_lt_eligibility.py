from datetime import date, timedelta
from decimal import Decimal

from net_alpha.inbox.models import Severity, SignalType
from net_alpha.inbox.signals.lt_eligibility import compute_lt_eligibility
from tests.inbox.conftest import make_lot, make_prices_stub, make_repo

# Marginal rates pulled from the user's tax: config (st_rate - lt_rate).
ST_RATE = Decimal("0.37")
LT_RATE = Decimal("0.20")


def test_lot_already_long_term_excluded():
    today = date(2026, 5, 1)
    acquired = today - timedelta(days=400)  # already past 366
    repo = make_repo(lots=[make_lot(acquired=acquired, ticker="AAPL", quantity=10, cost_basis=1000)])
    prices = make_prices_stub({"AAPL": Decimal("200")})
    items = compute_lt_eligibility(repo=repo, prices=prices, today=today, st_rate=ST_RATE, lt_rate=LT_RATE)
    assert items == []


def test_lot_outside_lookahead_excluded():
    today = date(2026, 5, 1)
    acquired = today - timedelta(days=305)  # 61 days to LT (> default 60)
    repo = make_repo(lots=[make_lot(acquired=acquired, ticker="AAPL", quantity=10, cost_basis=1000)])
    prices = make_prices_stub({"AAPL": Decimal("200")})
    items = compute_lt_eligibility(repo=repo, prices=prices, today=today, st_rate=ST_RATE, lt_rate=LT_RATE)
    assert items == []


def test_lot_inside_lookahead_with_gain_emits_item():
    today = date(2026, 5, 1)
    acquired = today - timedelta(days=306)  # 60 days to LT
    repo = make_repo(lots=[make_lot(lid="42", acquired=acquired, ticker="AAPL", quantity=10, cost_basis=1000)])
    prices = make_prices_stub({"AAPL": Decimal("200")})  # 200*10 - 1000 = 1000 gain
    items = compute_lt_eligibility(repo=repo, prices=prices, today=today, st_rate=ST_RATE, lt_rate=LT_RATE)
    assert len(items) == 1
    item = items[0]
    assert item.signal_type is SignalType.LT_ELIGIBLE
    assert item.dismiss_key == "lt_eligible:42"
    assert item.days_until == 60
    assert item.severity is Severity.INFO  # > 14 days
    assert item.dollar_impact == Decimal("170")  # 1000 * (0.37 - 0.20)
    assert item.deep_link == "/ticker/AAPL?lot=42"


def test_lot_within_14_days_is_watch_severity():
    today = date(2026, 5, 1)
    acquired = today - timedelta(days=352)  # 14 days to LT
    repo = make_repo(lots=[make_lot(acquired=acquired, ticker="AAPL", quantity=10, cost_basis=1000)])
    prices = make_prices_stub({"AAPL": Decimal("200")})
    items = compute_lt_eligibility(repo=repo, prices=prices, today=today, st_rate=ST_RATE, lt_rate=LT_RATE)
    assert len(items) == 1
    assert items[0].severity is Severity.WATCH


def test_lot_at_loss_skipped():
    today = date(2026, 5, 1)
    acquired = today - timedelta(days=350)
    repo = make_repo(lots=[make_lot(acquired=acquired, ticker="AAPL", quantity=10, cost_basis=2500)])
    prices = make_prices_stub({"AAPL": Decimal("200")})  # 2000 < 2500 → loss
    items = compute_lt_eligibility(repo=repo, prices=prices, today=today, st_rate=ST_RATE, lt_rate=LT_RATE)
    assert items == []


def test_missing_price_emits_item_without_dollar_impact():
    today = date(2026, 5, 1)
    acquired = today - timedelta(days=350)
    repo = make_repo(lots=[make_lot(acquired=acquired, ticker="GHOST", quantity=10, cost_basis=1000)])
    prices = make_prices_stub({})  # no quote
    items = compute_lt_eligibility(repo=repo, prices=prices, today=today, st_rate=ST_RATE, lt_rate=LT_RATE)
    assert len(items) == 1
    item = items[0]
    assert item.dollar_impact is None
    assert "(no price)" in item.subtitle


def test_lookahead_override_respected():
    today = date(2026, 5, 1)
    acquired = today - timedelta(days=305)  # 61 days to LT
    repo = make_repo(lots=[make_lot(acquired=acquired, ticker="AAPL", quantity=10, cost_basis=1000)])
    prices = make_prices_stub({"AAPL": Decimal("200")})
    items = compute_lt_eligibility(
        repo=repo,
        prices=prices,
        today=today,
        st_rate=ST_RATE,
        lt_rate=LT_RATE,
        lookahead_days=90,
    )
    assert len(items) == 1


def test_lot_at_exactly_366_days_excluded():
    """Boundary: a lot acquired exactly 366 days ago has days_until=0,
    which the > 0 guard correctly excludes (already long-term)."""
    today = date(2026, 5, 1)
    acquired = today - timedelta(days=366)
    repo = make_repo(lots=[make_lot(acquired=acquired, ticker="AAPL", quantity=10, cost_basis=1000)])
    prices = make_prices_stub({"AAPL": Decimal("200")})
    items = compute_lt_eligibility(repo=repo, prices=prices, today=today, st_rate=ST_RATE, lt_rate=LT_RATE)
    assert items == []


def test_account_filter_excludes_other_accounts():
    today = date(2026, 5, 1)
    acquired = today - timedelta(days=350)
    repo = make_repo(
        lots=[
            make_lot(lid="1", account="Schwab/A", acquired=acquired, ticker="A", quantity=1, cost_basis=10),
            make_lot(lid="2", account="Schwab/B", acquired=acquired, ticker="B", quantity=1, cost_basis=10),
        ]
    )
    prices = make_prices_stub({"A": Decimal("11"), "B": Decimal("11")})
    items = compute_lt_eligibility(
        repo=repo,
        prices=prices,
        today=today,
        st_rate=ST_RATE,
        lt_rate=LT_RATE,
        account="Schwab/A",
    )
    assert {i.dismiss_key for i in items} == {"lt_eligible:1"}
