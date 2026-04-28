"""Tests for the /tax tabbed page (Task 26-27)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from net_alpha.engine.detector import detect_in_window
from net_alpha.models.domain import Trade
from tests.web.conftest import seed_import as web_seed


@pytest.fixture
def schwab_account(repo):
    """Create a Schwab/Tax account."""
    return repo.get_or_create_account(broker="Schwab", label="Tax")


def _seed_uuuu_buy(repo, account, on: date, qty: int = 100, basis: int = 600) -> None:
    """Seed a single UUUU equity buy and populate lots."""
    web_seed(
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


def test_get_tax_default_view_renders_wash_sales_tab(client, repo, schwab_account):
    today = date.today()
    _seed_uuuu_buy(repo, schwab_account, today - timedelta(days=10))
    resp = client.get("/tax")
    assert resp.status_code == 200
    body = resp.text
    assert "Tax" in body
    assert "Wash sales" in body or "wash-sales" in body.lower()


def test_get_tax_view_harvest_renders_harvest_queue(client, repo, schwab_account):
    today = date.today()
    _seed_uuuu_buy(repo, schwab_account, today - timedelta(days=10))
    resp = client.get("/tax?view=harvest")
    assert resp.status_code == 200
    assert "harvest" in resp.text.lower()


def test_get_tax_view_budget_renders_offset_budget(client, repo, schwab_account):
    resp = client.get("/tax?view=budget")
    assert resp.status_code == 200
    assert "harvested" in resp.text.lower() or "cap" in resp.text.lower()


def test_get_tax_view_projection_renders_card_or_placeholder(client):
    resp = client.get("/tax?view=projection")
    assert resp.status_code == 200
    assert "projection" in resp.text.lower() or "tax bracket" in resp.text.lower()
