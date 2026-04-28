"""Phase 2 end-to-end smoke: every new surface renders without 500s on a small
multi-account dataset that exercises wheel awareness, harvest queue, projection."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from net_alpha.engine.detector import detect_in_window
from net_alpha.models.domain import OptionDetails, Trade


@pytest.fixture
def schwab_account(repo):
    """Create a Schwab/Tax account for Phase 2 smoke tests."""
    return repo.get_or_create_account(broker="Schwab", label="Tax")


def _seed_phase2_dataset(repo, schwab_account):
    """Seed a CSP-assigned chain + a long-term equity buy."""
    today = date.today()
    sto = Trade(
        account=schwab_account.display(),
        date=today - timedelta(days=180),
        ticker="UUUU",
        action="Sell to Open",
        quantity=Decimal("1"),
        proceeds=Decimal("120"),
        cost_basis=Decimal("0"),
        option_details=OptionDetails(strike=Decimal("5"), expiry=today - timedelta(days=120), call_put="P"),
        basis_source="option_short_open",
    )
    btc = Trade(
        account=schwab_account.display(),
        date=today - timedelta(days=120),
        ticker="UUUU",
        action="Buy to Close",
        quantity=Decimal("1"),
        proceeds=Decimal("0"),
        cost_basis=Decimal("0"),
        option_details=OptionDetails(strike=Decimal("5"), expiry=today - timedelta(days=120), call_put="P"),
        basis_source="option_short_close_assigned",
    )
    assigned = Trade(
        account=schwab_account.display(),
        date=today - timedelta(days=120),
        ticker="UUUU",
        action="Buy",
        quantity=Decimal("100"),
        proceeds=Decimal("0"),
        cost_basis=Decimal("380"),
        basis_source="option_short_open_assigned",
    )
    spy_buy = Trade(
        account=schwab_account.display(),
        date=today - timedelta(days=400),
        ticker="SPY",
        action="Buy",
        quantity=Decimal("10"),
        proceeds=Decimal("0"),
        cost_basis=Decimal("4500"),
    )
    from tests.web.conftest import seed_import as web_seed

    web_seed(repo, schwab_account.broker, schwab_account.label, [sto, btc, assigned, spy_buy])

    # Populate lots so harvest queue can find them.
    trades = repo.all_trades()
    if trades:
        result = detect_in_window(
            trades,
            min(t.date for t in trades),
            max(t.date for t in trades),
            etf_pairs={},
        )
        repo.replace_lots_in_window(
            min(t.date for t in trades),
            max(t.date for t in trades),
            result.lots,
        )


def test_phase2_full_smoke(client, repo, schwab_account):
    today = date.today()
    _seed_phase2_dataset(repo, schwab_account)

    # /tax — every tab renders without 500.
    for view in ("wash-sales", "harvest", "budget", "projection"):
        resp = client.get(f"/tax?view={view}")
        assert resp.status_code == 200, f"/tax?view={view} returned {resp.status_code}"

    # /portfolio/kpis renders the offset-budget tile and projection card.
    resp = client.get("/portfolio/kpis")
    assert resp.status_code == 200

    # /wash-sales -> /tax 301.
    resp = client.get("/wash-sales", follow_redirects=False)
    assert resp.status_code == 301
    assert resp.headers["location"].startswith("/tax")

    # /sim — POST renders traffic light fragment.
    resp = client.post(
        "/sim",
        data={
            "action": "sell",
            "ticker": "UUUU",
            "qty": "100",
            "price": "3",
            "account": schwab_account.display(),
            "trade_date": today.isoformat(),
        },
    )
    assert resp.status_code == 200
    assert "traffic-light" in resp.text
