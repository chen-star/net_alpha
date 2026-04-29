"""C4 smoke test: exempt matches in the DB render on the wash-sales tab.

Verifies:
- The §1256 exempt matches table is present in the page when exempt matches exist.
- Individual exempt match rows show the ticker, exempt reason, and notional disallowed.
- I1: The HTMX explain target is a <td>, not a <tr>, so innerHTML swap produces valid HTML.
- The exempt section is absent when there are no exempt matches.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from net_alpha.models.domain import ExemptMatch, Trade


def _seed_violation_and_exempt(repo, builders):
    """Seed trades, a violation, and an exempt match so both sections render."""
    from datetime import date as _date
    from decimal import Decimal as _D

    from sqlmodel import Session

    from net_alpha.db.tables import WashSaleViolationRow

    # Seed TSLA wash sale (violation section)
    builders.seed_import(
        repo,
        "schwab",
        "main",
        [
            Trade(
                account="schwab/main",
                date=_date(2025, 3, 1),
                ticker="TSLA",
                action="Sell",
                quantity=_D("10"),
                proceeds=_D("1500"),
                cost_basis=_D("2000"),
            ),
            Trade(
                account="schwab/main",
                date=_date(2025, 3, 15),
                ticker="TSLA",
                action="Buy",
                quantity=_D("10"),
                proceeds=None,
                cost_basis=_D("1550"),
            ),
        ],
    )

    # Seed SPX exempt match
    builders.seed_import(
        repo,
        "schwab",
        "main",
        [
            Trade(
                account="schwab/main",
                date=_date(2025, 4, 1),
                ticker="SPX",
                action="Sell",
                quantity=_D("2"),
                proceeds=_D("200"),
                cost_basis=_D("1443"),
            ),
            Trade(
                account="schwab/main",
                date=_date(2025, 4, 8),
                ticker="SPX",
                action="Buy",
                quantity=_D("2"),
                proceeds=None,
                cost_basis=_D("300"),
            ),
        ],
        csv_filename="spx_seed.csv",
    )

    saved = repo.all_trades()
    tsla_sell = next(t for t in saved if t.ticker == "TSLA" and t.action == "Sell")
    tsla_buy = next(t for t in saved if t.ticker == "TSLA" and t.action == "Buy")
    spx_sell = next(t for t in saved if t.ticker == "SPX" and t.action == "Sell")
    spx_buy = next(t for t in saved if t.ticker == "SPX" and t.action == "Buy")
    acct_row = repo.list_accounts()[0]

    with Session(repo.engine) as session:
        vrow = WashSaleViolationRow(
            loss_trade_id=int(tsla_sell.id),
            replacement_trade_id=int(tsla_buy.id),
            loss_account_id=acct_row.id,
            buy_account_id=acct_row.id,
            loss_sale_date=tsla_sell.date.isoformat(),
            triggering_buy_date=tsla_buy.date.isoformat(),
            ticker="TSLA",
            confidence="Confirmed",
            disallowed_loss=500.0,
            matched_quantity=10.0,
            source="engine",
        )
        session.add(vrow)
        session.commit()

    em = ExemptMatch(
        loss_trade_id=spx_sell.id,
        triggering_buy_id=spx_buy.id,
        exempt_reason="section_1256",
        rule_citation="IRC §1256(c)",
        notional_disallowed=_D("1243"),
        confidence="Confirmed",
        matched_quantity=2.0,
        loss_account="schwab/main",
        buy_account="schwab/main",
        loss_sale_date=spx_sell.date,
        triggering_buy_date=spx_buy.date,
        ticker="SPX",
    )
    repo.save_exempt_matches([em])


def test_exempt_matches_render_on_wash_sales_tab(client: TestClient, repo, builders):
    """Exempt matches in the DB appear in the wash-sales tab HTML."""
    _seed_violation_and_exempt(repo, builders)

    # Use year=0 to show "All years" (avoids filtering out 2025 data if today is 2026).
    res = client.get("/tax?view=table&year=0", follow_redirects=True)
    assert res.status_code == 200

    # The exempt matches table section should be rendered.
    assert 'data-testid="exempt-matches-table"' in res.text, (
        "Expected exempt-matches-table testid in page HTML when exempt matches exist"
    )
    # The SPX ticker should appear.
    assert "SPX" in res.text
    # The exempt reason text should appear (rendered as "Section 1256" after title-case filter).
    assert "1256" in res.text
    # Section header should be present.
    assert "1256 Exempt Matches" in res.text


def test_exempt_matches_htmx_target_is_td_not_tr(client: TestClient, repo, builders):
    """I1: The HTMX explain row puts the id on the <td>, not the <tr>.

    The fix moves the id from <tr id="violation-N-explain"> to
    <td id="violation-N-explain">, so HTMX innerHTML swap inserts into the
    <td> container — producing valid table HTML. A <div> fragment swapped
    into a <tr> would be hoisted out of the table by browsers.
    """
    import re

    _seed_violation_and_exempt(repo, builders)

    res = client.get("/tax?view=table&year=0", follow_redirects=True)
    assert res.status_code == 200
    html = res.text

    # Bad pattern (I1 bug): id on <tr>
    bad_pattern = re.compile(r'<tr[^>]*id="violation-\d+-explain"')
    assert not bad_pattern.search(html), (
        "I1 bug: found violation explain id on <tr> — must be on <td> for valid table HTML"
    )

    # Good pattern: id on <td>
    good_pattern = re.compile(r'<td[^>]*id="violation-\d+-explain"')
    assert good_pattern.search(html), (
        "Expected violation explain id on a <td> element for valid HTMX innerHTML swap target"
    )

    # Mirror check: exempt match explain rows must also have id on <td>.
    bad_exempt = re.compile(r'<tr[^>]*id="exempt-\d+-explain"')
    assert not bad_exempt.search(html), "I1 bug (exempt rows): found exempt explain id on <tr> — must be on <td>"
    good_exempt = re.compile(r'<td[^>]*id="exempt-\d+-explain"')
    assert good_exempt.search(html), "Expected exempt explain id on a <td> element (mirrors violation row fix)"


def test_no_exempt_section_when_no_exempt_matches(client: TestClient, repo, builders):
    """When there are no exempt matches, the exempt section must not render."""
    # Seed a violation but no exempt match.
    from datetime import date as _date
    from decimal import Decimal as _D

    from sqlmodel import Session

    from net_alpha.db.tables import WashSaleViolationRow

    builders.seed_import(
        repo,
        "schwab",
        "main",
        [
            Trade(
                account="schwab/main",
                date=_date(2025, 5, 1),
                ticker="AAPL",
                action="Sell",
                quantity=_D("5"),
                proceeds=_D("900"),
                cost_basis=_D("1200"),
            ),
            Trade(
                account="schwab/main",
                date=_date(2025, 5, 10),
                ticker="AAPL",
                action="Buy",
                quantity=_D("5"),
                proceeds=None,
                cost_basis=_D("950"),
            ),
        ],
    )
    saved = repo.all_trades()
    sell = next(t for t in saved if t.action == "Sell")
    buy = next(t for t in saved if t.action == "Buy")
    acct_row = repo.list_accounts()[0]
    with Session(repo.engine) as session:
        session.add(
            WashSaleViolationRow(
                loss_trade_id=int(sell.id),
                replacement_trade_id=int(buy.id),
                loss_account_id=acct_row.id,
                buy_account_id=acct_row.id,
                loss_sale_date=sell.date.isoformat(),
                triggering_buy_date=buy.date.isoformat(),
                ticker="AAPL",
                confidence="Confirmed",
                disallowed_loss=300.0,
                matched_quantity=5.0,
                source="engine",
            )
        )
        session.commit()

    res = client.get("/tax?view=table&year=0", follow_redirects=True)
    assert res.status_code == 200
    assert 'data-testid="exempt-matches-table"' not in res.text, (
        "Exempt matches section must not render when there are no exempt matches"
    )
