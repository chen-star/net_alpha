"""HTMX fragment endpoints for inline-expand explanations.

Tests: /tax/violation/{vid}/explain and /tax/exempt/{eid}/explain
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session

from net_alpha.db.tables import WashSaleViolationRow
from net_alpha.models.domain import ExemptMatch, Trade

# ---------------------------------------------------------------------------
# Helpers — use the conftest fixtures (client, repo, builders) via pytest
# ---------------------------------------------------------------------------


def _seed_tsla_violation(repo, builders):
    """Seed a TSLA sell (loss) + buy within 30 days, then inject a violation row.

    Returns the WashSaleViolationRow id.
    """
    acct, _ = builders.seed_import(
        repo,
        "schwab",
        "main",
        [
            Trade(
                account="schwab/main",
                date=date(2025, 3, 1),
                ticker="TSLA",
                action="Sell",
                quantity=Decimal("10"),
                proceeds=Decimal("1500"),
                cost_basis=Decimal("2000"),
            ),
            Trade(
                account="schwab",  # any string — just needs to exist
                date=date(2025, 3, 15),
                ticker="TSLA",
                action="Buy",
                quantity=Decimal("10"),
                proceeds=None,
                cost_basis=Decimal("1550"),
            ),
        ],
    )
    saved = repo.all_trades()
    sell = next(t for t in saved if t.action == "Sell" and t.ticker == "TSLA")
    buy = next(t for t in saved if t.action == "Buy" and t.ticker == "TSLA")
    acct_row = repo.list_accounts()[0]

    with Session(repo.engine) as session:
        vrow = WashSaleViolationRow(
            loss_trade_id=int(sell.id),
            replacement_trade_id=int(buy.id),
            loss_account_id=acct_row.id,
            buy_account_id=acct_row.id,
            loss_sale_date=sell.date.isoformat(),
            triggering_buy_date=buy.date.isoformat(),
            ticker="TSLA",
            confidence="Confirmed",
            disallowed_loss=500.0,
            matched_quantity=10.0,
            source="engine",
        )
        session.add(vrow)
        session.commit()
        session.refresh(vrow)
        return vrow.id


def _seed_spx_exempt(repo, builders):
    """Seed an SPX sell (loss) + buy and inject an ExemptMatchRow.

    Returns the ExemptMatchRow id.
    """
    builders.seed_import(
        repo,
        "schwab",
        "main",
        [
            Trade(
                account="schwab/main",
                date=date(2025, 4, 1),
                ticker="SPX",
                action="Sell",
                quantity=Decimal("1"),
                proceeds=Decimal("100"),
                cost_basis=Decimal("721"),
            ),
            Trade(
                account="schwab/main",
                date=date(2025, 4, 8),
                ticker="SPX",
                action="Buy",
                quantity=Decimal("1"),
                proceeds=None,
                cost_basis=Decimal("200"),
            ),
        ],
    )
    saved = repo.all_trades()
    sell = next(t for t in saved if t.action == "Sell" and t.ticker == "SPX")
    buy = next(t for t in saved if t.action == "Buy" and t.ticker == "SPX")

    exempt = ExemptMatch(
        loss_trade_id=sell.id,
        triggering_buy_id=buy.id,
        exempt_reason="section_1256",
        rule_citation="IRC §1256(c)",
        notional_disallowed=Decimal("621"),
        confidence="Confirmed",
        matched_quantity=1.0,
        loss_account="schwab/main",
        buy_account="schwab/main",
        loss_sale_date=sell.date,
        triggering_buy_date=buy.date,
        ticker="SPX",
    )
    repo.save_exempt_matches([exempt])

    matches = repo.list_exempt_matches()
    return matches[0].id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_violation_explain_fragment_returns_200(client: TestClient, repo, builders):
    vid = _seed_tsla_violation(repo, builders)
    r = client.get(f"/tax/violation/{vid}/explain")
    assert r.status_code == 200
    assert "TSLA" in r.text
    assert "exact ticker" in r.text.lower()


def test_exempt_explain_fragment_returns_200(client: TestClient, repo, builders):
    _seed_tsla_violation(repo, builders)  # ensures sell/buy trades exist first
    eid = _seed_spx_exempt(repo, builders)
    r = client.get(f"/tax/exempt/{eid}/explain")
    assert r.status_code == 200
    assert "1256" in r.text
    assert "SPX" in r.text


def test_violation_explain_fragment_404_for_unknown_id(client: TestClient):
    r = client.get("/tax/violation/999999/explain")
    assert r.status_code == 404
