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


def test_account_filter_query_param_scopes_signals(client, repo):
    """The ?account=X query param must narrow signals to that account."""
    from datetime import date, timedelta
    from datetime import datetime as _datetime

    from net_alpha.models.domain import ImportRecord, Trade, WashSaleViolation

    today = date.today()
    sale_date = today - timedelta(days=33)
    buy_date = sale_date - timedelta(days=10)

    # Two accounts, each with its own wash-sale violation on a different ticker.
    acct_a = repo.get_or_create_account("Schwab", "A")
    acct_b = repo.get_or_create_account("Schwab", "B")

    def _seed(account, ticker):
        buy = Trade(
            account=f"Schwab/{account.label}",
            date=buy_date,
            ticker=ticker,
            action="Buy",
            quantity=10,
            proceeds=None,
            cost_basis=2000.0,
        )
        sell = Trade(
            account=f"Schwab/{account.label}",
            date=sale_date,
            ticker=ticker,
            action="Sell",
            quantity=10,
            proceeds=1388.0,
            cost_basis=2000.0,
        )
        record = ImportRecord(
            account_id=account.id,
            csv_filename=f"{ticker}.csv",
            csv_sha256=f"sha-{ticker}",
            imported_at=_datetime.now(),
            trade_count=2,
        )
        repo.add_import(account, record, [buy, sell])

    _seed(acct_a, "AAPL")
    _seed(acct_b, "GOOG")

    # Map back to persisted trade ids per ticker for the violation rows.
    trades = repo.all_trades()
    aapl_buy = next(t for t in trades if t.ticker == "AAPL" and t.is_buy())
    aapl_sell = next(t for t in trades if t.ticker == "AAPL" and t.is_sell())
    goog_buy = next(t for t in trades if t.ticker == "GOOG" and t.is_buy())
    goog_sell = next(t for t in trades if t.ticker == "GOOG" and t.is_sell())

    repo.replace_violations_in_window(
        sale_date,
        sale_date,
        [
            WashSaleViolation(
                loss_trade_id=aapl_sell.id,
                replacement_trade_id=aapl_buy.id,
                confidence="Confirmed",
                disallowed_loss=612.0,
                matched_quantity=10.0,
                ticker="AAPL",
                loss_account="Schwab/A",
                buy_account="Schwab/A",
                loss_sale_date=sale_date,
                triggering_buy_date=buy_date,
            ),
            WashSaleViolation(
                loss_trade_id=goog_sell.id,
                replacement_trade_id=goog_buy.id,
                confidence="Confirmed",
                disallowed_loss=612.0,
                matched_quantity=10.0,
                ticker="GOOG",
                loss_account="Schwab/B",
                buy_account="Schwab/B",
                loss_sale_date=sale_date,
                triggering_buy_date=buy_date,
            ),
        ],
    )

    # No filter: both tickers visible.
    resp = client.get("/portfolio/inbox")
    assert "AAPL" in resp.text
    assert "GOOG" in resp.text

    # Schwab/A filter: only AAPL.
    resp = client.get("/portfolio/inbox?account=Schwab/A")
    assert "AAPL" in resp.text
    assert "GOOG" not in resp.text

    # Schwab/B filter: only GOOG.
    resp = client.get("/portfolio/inbox?account=Schwab/B")
    assert "GOOG" in resp.text
    assert "AAPL" not in resp.text
