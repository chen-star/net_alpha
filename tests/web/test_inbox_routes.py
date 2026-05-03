"""Tests for the Action Inbox routes (GET /portfolio/inbox + POST dismiss).

Uses the standard `client` + `repo` fixtures from tests/web/conftest.py.
Seeds wash-sale violations directly via repo.replace_violations_in_window
since that's the cheapest way to get a deterministic InboxItem set.
"""

from __future__ import annotations

from datetime import date, timedelta
from datetime import datetime as _datetime

from net_alpha.models.domain import Trade, WashSaleViolation


def _seed_one_safe_to_rebuy(repo, *, account_label: str = "Tax", days_ago: int = 33):
    """Create an account + a single closed wash-sale-triggering trade pair,
    then write a violation directly.

    Returns the violation id (str)."""
    account = repo.get_or_create_account("Schwab", account_label)
    today = date.today()
    sale_date = today - timedelta(days=days_ago)

    # Buy then sell — both real Trade rows so violation FK constraints succeed.
    buy = Trade(
        account=f"Schwab/{account_label}",
        date=sale_date - timedelta(days=10),
        ticker="AAPL",
        action="Buy",
        quantity=10,
        proceeds=None,
        cost_basis=2000.0,
    )
    sell = Trade(
        account=f"Schwab/{account_label}",
        date=sale_date,
        ticker="AAPL",
        action="Sell",
        quantity=10,
        proceeds=1388.0,
        cost_basis=2000.0,
    )

    from net_alpha.models.domain import ImportRecord

    record = ImportRecord(
        account_id=account.id,
        csv_filename="seed.csv",
        csv_sha256="seed",
        imported_at=_datetime.now(),
        trade_count=2,
    )
    repo.add_import(account, record, [buy, sell])

    # Find the actual saved trade ids.
    trades = repo.all_trades()
    sell_t = next(t for t in trades if t.ticker == "AAPL" and t.is_sell())
    buy_t = next(t for t in trades if t.ticker == "AAPL" and t.is_buy())

    # Write a violation row covering the sale.
    v = WashSaleViolation(
        loss_trade_id=sell_t.id,
        replacement_trade_id=buy_t.id,
        confidence="Confirmed",
        disallowed_loss=612.0,
        matched_quantity=10.0,
        ticker="AAPL",
        loss_account=f"Schwab/{account_label}",
        buy_account=f"Schwab/{account_label}",
        loss_sale_date=sale_date,
        triggering_buy_date=sale_date - timedelta(days=10),
    )
    repo.replace_violations_in_window(sale_date, sale_date, [v])

    # Return the persisted violation id (string-of-int from repo.all_violations).
    persisted = repo.all_violations()
    return persisted[0].id


def test_inbox_endpoint_returns_html_fragment(client, repo):
    _seed_one_safe_to_rebuy(repo)
    resp = client.get("/portfolio/inbox")
    assert resp.status_code == 200
    body = resp.text
    assert "AAPL" in body


def test_dismiss_endpoint_hides_item_on_next_load(client, repo):
    vid = _seed_one_safe_to_rebuy(repo)

    # First load: item present.
    resp = client.get("/portfolio/inbox")
    assert "AAPL" in resp.text

    # Dismiss it.
    resp = client.post(f"/portfolio/inbox/dismiss/wash_rebuy:{vid}")
    assert resp.status_code == 200

    # Second load: item gone.
    resp = client.get("/portfolio/inbox")
    assert "AAPL" not in resp.text


def test_dismiss_unknown_key_is_noop(client, repo):
    # No data; just hit the endpoint with a bogus key.
    resp = client.post("/portfolio/inbox/dismiss/does:not:exist")
    assert resp.status_code == 200
