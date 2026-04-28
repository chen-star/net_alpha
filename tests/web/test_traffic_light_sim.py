from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from net_alpha.engine.detector import detect_in_window
from net_alpha.models.domain import Trade
from tests.web.conftest import seed_import as web_seed_import


@pytest.fixture
def schwab_account(repo):
    """Create a Schwab/Tax account for traffic-light sim tests."""
    return repo.get_or_create_account(broker="Schwab", label="Tax")


def _seed_uuuu_buy(repo, account, on: date, qty: int = 100, basis: int = 600) -> None:
    """Seed a single UUUU equity buy and populate lots."""
    web_seed_import(
        repo,
        account.broker,
        account.label,
        [
            Trade(
                account=account.display(),
                date=on,
                ticker="UUUU",
                action="Buy",
                quantity=Decimal(qty),
                proceeds=Decimal("0"),
                cost_basis=Decimal(basis),
            )
        ],
    )
    trades = repo.all_trades()
    if trades:
        min_date = min(t.date for t in trades)
        max_date = max(t.date for t in trades)
        result = detect_in_window(trades, min_date, max_date, etf_pairs={})
        repo.replace_lots_in_window(min_date, max_date, result.lots)


def test_sim_sell_post_shows_red_traffic_light_on_wash(client, repo, schwab_account):
    today = date.today()
    _seed_uuuu_buy(repo, schwab_account, today - timedelta(days=10))
    resp = client.post(
        "/sim",
        data={
            "action": "sell",
            "ticker": "UUUU",
            "qty": "100",
            "price": "4",
            "account": schwab_account.display(),
            "trade_date": today.isoformat(),
        },
    )
    assert resp.status_code == 200
    assert "traffic-light" in resp.text


def test_sim_buy_post_shows_traffic_light_fragment(client, repo, schwab_account):
    today = date.today()
    resp = client.post(
        "/sim",
        data={
            "action": "buy",
            "ticker": "UUUU",
            "qty": "10",
            "price": "5",
            "account": schwab_account.display(),
            "trade_date": today.isoformat(),
        },
    )
    assert resp.status_code == 200
    assert "traffic-light" in resp.text
