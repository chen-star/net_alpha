"""/tax page must expose a Period selector (YTD / year / Lifetime).

Regression: the Tax page only had an Account selector while Portfolio,
Positions, and Sim all carry a Period selector in the toolbar. CLAUDE.md
explicitly documents the Period+Account convention as "State is per-page";
Tax was the only scoped page violating it. Without it, the Performance
panel was permanently YTD and the user couldn't see prior-year breakdowns.

Acceptance:
- The form posts ?period=<value> with values "ytd", "<year>", or "lifetime".
- Default selection is "ytd" when no period is specified.
- A selected period round-trips on re-render.
"""

from __future__ import annotations

from datetime import date

from tests.web.conftest import make_buy, make_sell, seed_import


def test_tax_page_renders_period_selector(client, repo):
    """The toolbar must include a Period dropdown."""
    seed_import(
        repo,
        "schwab",
        "personal",
        [
            make_buy("schwab/personal", "SPY", date(2024, 1, 15), qty=10, cost=4000),
            make_sell(
                "schwab/personal",
                "SPY",
                date(2024, 6, 15),
                qty=5,
                proceeds=2400,
                cost=2000,
            ),
        ],
    )
    r = client.get("/tax?view=performance")
    assert r.status_code == 200
    body = r.text
    # Period selector must exist with the three canonical values.
    assert 'name="period"' in body
    assert 'value="ytd"' in body
    assert 'value="lifetime"' in body
    # Default (no ?period= param) selects YTD.
    assert 'value="ytd" selected' in body


def test_tax_period_lifetime_renders(client, repo):
    """?period=lifetime must reach the page intact and be selected."""
    seed_import(
        repo,
        "schwab",
        "personal",
        [
            make_buy("schwab/personal", "SPY", date(2024, 1, 15), qty=10, cost=4000),
            make_sell(
                "schwab/personal",
                "SPY",
                date(2024, 6, 15),
                qty=5,
                proceeds=2400,
                cost=2000,
            ),
        ],
    )
    r = client.get("/tax?view=performance&period=lifetime")
    assert r.status_code == 200
    body = r.text
    assert 'value="lifetime" selected' in body


def test_tax_period_explicit_year_renders(client, repo):
    """?period=2024 must select 2024 in the dropdown."""
    seed_import(
        repo,
        "schwab",
        "personal",
        [
            make_buy("schwab/personal", "SPY", date(2024, 1, 15), qty=10, cost=4000),
            make_sell(
                "schwab/personal",
                "SPY",
                date(2024, 6, 15),
                qty=5,
                proceeds=2400,
                cost=2000,
            ),
        ],
    )
    r = client.get("/tax?view=performance&period=2024")
    assert r.status_code == 200
    body = r.text
    assert 'value="2024" selected' in body
