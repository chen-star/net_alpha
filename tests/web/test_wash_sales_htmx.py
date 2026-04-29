"""Verify the wash-sales template includes HTMX attrs after Task 14 wiring.

Each violation row must carry hx-get, hx-trigger, hx-target, hx-swap and the
sibling explain row must exist so the fragment has a DOM target.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session

from net_alpha.db.tables import WashSaleViolationRow
from net_alpha.models.domain import Trade

# ---------------------------------------------------------------------------
# Helpers — mirror the seeding pattern from test_explain_fragment.py
# ---------------------------------------------------------------------------


def _seed_violation(repo, builders) -> int:
    """Seed a TSLA sell (loss) + buy within 30 days and inject a violation row.

    Returns the WashSaleViolationRow id.
    """
    acct, _ = builders.seed_import(
        repo,
        "schwab",
        "main",
        [
            Trade(
                account="schwab/main",
                date=date(2026, 3, 1),
                ticker="TSLA",
                action="Sell",
                quantity=Decimal("10"),
                proceeds=Decimal("1500"),
                cost_basis=Decimal("2000"),
            ),
            Trade(
                account="schwab/main",
                date=date(2026, 3, 15),
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_wash_sales_table_includes_htmx_attrs(client: TestClient, repo, builders):
    """Render /tax?view=wash-sales and confirm violation rows carry HTMX attrs."""
    vid = _seed_violation(repo, builders)

    res = client.get("/tax?view=wash-sales", follow_redirects=True)
    assert res.status_code == 200
    html = res.text

    # Data row must carry HTMX inline-expand attributes.
    assert f'id="violation-{vid}"' in html
    assert f'hx-get="/tax/violation/{vid}/explain"' in html
    assert 'hx-trigger="click once"' in html
    assert f'hx-target="#violation-{vid}-explain"' in html
    assert 'hx-swap="innerHTML"' in html

    # Alpine toggle must be on the scoping tbody (or the row itself).
    assert '@click="open = !open"' in html

    # Sibling explain row must exist in the DOM as the HTMX target.
    assert f'id="violation-{vid}-explain"' in html

    # Row should be styled as clickable.
    assert "cursor-pointer" in html


def test_wash_sales_explain_row_has_correct_colspan(client: TestClient, repo, builders):
    """The explain <td> must span all 8 columns so the fragment fills the row."""
    _seed_violation(repo, builders)

    res = client.get("/tax?view=wash-sales", follow_redirects=True)
    assert res.status_code == 200

    # The explain row td must span 8 columns (the violation table has 8).
    assert 'colspan="8"' in res.text
