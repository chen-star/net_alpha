"""Multi-account filter behavior on the wash-sales tab — including OR semantics
for cross-account violations (Rev. Rul. 2008-5 makes this matter)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from net_alpha.db.tables import WashSaleViolationRow
from net_alpha.models.domain import Trade


# ---------------------------------------------------------------------------
# Basic HTTP tests — empty DB, just checking routing and status codes
# ---------------------------------------------------------------------------


def test_wash_sales_repeated_account_query_returns_200(client: TestClient):
    resp = client.get(
        "/tax",
        params=[("view", "wash-sales"), ("account", "Schwab/Tax"), ("account", "Schwab/IRA")],
    )
    assert resp.status_code == 200


def test_wash_sales_legacy_single_account_query_works(client: TestClient):
    resp = client.get("/tax?view=wash-sales&account=Schwab%2FTax")
    assert resp.status_code == 200


def test_wash_sales_empty_account_query_returns_200(client: TestClient):
    resp = client.get("/tax?view=wash-sales&account=")
    assert resp.status_code == 200


def test_wash_sales_no_account_query_returns_200(client: TestClient):
    resp = client.get("/tax?view=wash-sales")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# OR-semantic test: a cross-account violation appears under EITHER side's filter
# ---------------------------------------------------------------------------


def _seed_cross_account_violation(repo, builders) -> tuple[str, str]:
    """Seed a violation with loss in acct-A and replacement buy in acct-B.

    Returns (loss_account_display, buy_account_display).
    """
    acct_a, _ = builders.seed_import(
        repo,
        "schwab",
        "Tax",
        [
            Trade(
                account="schwab/Tax",
                date=date(2026, 1, 10),
                ticker="AAPL",
                action="Sell",
                quantity=Decimal("10"),
                proceeds=Decimal("1500"),
                cost_basis=Decimal("2000"),
            ),
        ],
    )
    acct_b, _ = builders.seed_import(
        repo,
        "schwab",
        "IRA",
        [
            Trade(
                account="schwab/IRA",
                date=date(2026, 1, 20),
                ticker="AAPL",
                action="Buy",
                quantity=Decimal("10"),
                proceeds=None,
                cost_basis=Decimal("1550"),
            ),
        ],
    )

    trades = repo.all_trades()
    sell = next(t for t in trades if t.action == "Sell" and t.ticker == "AAPL")
    buy = next(t for t in trades if t.action == "Buy" and t.ticker == "AAPL")

    with Session(repo.engine) as session:
        vrow = WashSaleViolationRow(
            loss_trade_id=int(sell.id),
            replacement_trade_id=int(buy.id),
            loss_account_id=acct_a.id,
            buy_account_id=acct_b.id,
            loss_sale_date=sell.date.isoformat(),
            triggering_buy_date=buy.date.isoformat(),
            ticker="AAPL",
            confidence="Confirmed",
            disallowed_loss=500.0,
            matched_quantity=10.0,
            source="engine",
            kind="permanent_ira",
        )
        session.add(vrow)
        session.commit()

    return f"{acct_a.broker}/{acct_a.label}", f"{acct_b.broker}/{acct_b.label}"


def test_cross_account_violation_appears_under_loss_account_filter(client: TestClient, repo, builders):
    """OR semantic: filtering by the loss account shows the cross-account violation."""
    loss_acct, _buy_acct = _seed_cross_account_violation(repo, builders)

    from net_alpha.web.routes.wash_sales import _wash_sales_context

    ctx = _wash_sales_context(repo, accounts=[loss_acct], year=2026)
    assert len(ctx["violations"]) == 1, (
        f"Expected 1 violation under loss-account filter '{loss_acct}', "
        f"got {len(ctx['violations'])}"
    )


def test_cross_account_violation_appears_under_buy_account_filter(client: TestClient, repo, builders):
    """OR semantic: filtering by the buy account also shows the cross-account violation."""
    _loss_acct, buy_acct = _seed_cross_account_violation(repo, builders)

    from net_alpha.web.routes.wash_sales import _wash_sales_context

    ctx = _wash_sales_context(repo, accounts=[buy_acct], year=2026)
    assert len(ctx["violations"]) == 1, (
        f"Expected 1 violation under buy-account filter '{buy_acct}', "
        f"got {len(ctx['violations'])}"
    )


def test_cross_account_violation_appears_under_both_accounts_filter(client: TestClient, repo, builders):
    """OR semantic: filtering by both accounts does not double-count the violation."""
    loss_acct, buy_acct = _seed_cross_account_violation(repo, builders)

    from net_alpha.web.routes.wash_sales import _wash_sales_context

    ctx = _wash_sales_context(repo, accounts=[loss_acct, buy_acct], year=2026)
    assert len(ctx["violations"]) == 1, (
        f"Expected exactly 1 violation (no double-count) under both-accounts filter, "
        f"got {len(ctx['violations'])}"
    )


def test_cross_account_violation_hidden_under_unrelated_account_filter(client: TestClient, repo, builders):
    """A filter for an unrelated account should not show the violation."""
    _seed_cross_account_violation(repo, builders)

    from net_alpha.web.routes.wash_sales import _wash_sales_context

    ctx = _wash_sales_context(repo, accounts=["schwab/Other"], year=2026)
    assert len(ctx["violations"]) == 0, (
        f"Expected 0 violations under unrelated-account filter, "
        f"got {len(ctx['violations'])}"
    )


def test_wash_sales_context_no_accounts_returns_all_violations(client: TestClient, repo, builders):
    """Empty accounts list means no filter — all violations visible."""
    _seed_cross_account_violation(repo, builders)

    from net_alpha.web.routes.wash_sales import _wash_sales_context

    ctx = _wash_sales_context(repo, accounts=[], year=2026)
    assert len(ctx["violations"]) == 1


def test_wash_sales_context_exposes_selected_accounts_key(client: TestClient, repo, builders):
    """Context dict must contain selected_accounts and accounts_available keys."""
    _seed_cross_account_violation(repo, builders)

    from net_alpha.web.routes.wash_sales import _wash_sales_context

    ctx = _wash_sales_context(repo, accounts=["schwab/Tax"])
    assert "selected_accounts" in ctx
    assert "accounts_available" in ctx
    assert "account_filter_active" in ctx
    # The old single-account key must be gone.
    assert "filter_account" not in ctx


def test_wash_sales_http_multi_account_returns_200_with_data(client_with_data: TestClient):
    """With real demo data, multi-account filter on the wash-sales tab is 200."""
    resp = client_with_data.get(
        "/tax",
        params=[("view", "wash-sales"), ("account", "Schwab/Tax"), ("account", "Schwab/IRA")],
    )
    assert resp.status_code == 200
