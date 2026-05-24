"""Audit #27, #28, #29 — links/forms inside scoped pages must round-trip the
page-level `period` and `account` selections so the user doesn't get bumped
back to the default scope when they switch tabs, sort a column, reset the
filter form, or toggle the harvestable-only checkbox.

Each test seeds enough data to render the relevant tab/view, then hits the
page with explicit `?period=...&account=...` query strings and asserts the
constructed URLs in the response preserve those values.

URL-encoding note: Jinja's `urlencode` filter uses `quote_plus`-style escaping
that leaves `/` alone — so `schwab/personal` round-trips as `schwab/personal`
in hrefs (browsers/Starlette accept this).
"""

from __future__ import annotations

from datetime import date

from net_alpha.models.domain import WashSaleViolation
from tests.web.conftest import make_buy, seed_import

_YR = 2024


def _seed_wash_violations(repo) -> None:
    repo.get_or_create_account("schwab", "personal")
    vs = [
        WashSaleViolation(
            loss_trade_id=str(i),
            replacement_trade_id=str(i),
            confidence="Confirmed",
            disallowed_loss=200.0 + i * 10,
            matched_quantity=10.0,
            ticker="TSLA",
            loss_account="schwab/personal",
            buy_account="schwab/personal",
            loss_sale_date=date(_YR, 6, 1 + i),
            triggering_buy_date=date(_YR, 6, 12 + i),
            source="engine",
        )
        for i in range(2)
    ]
    repo.replace_violations_in_window(date(_YR, 1, 1), date(_YR, 12, 31), vs)


# ---- audit #27 — Tax tab links drop `period` -------------------------------


def test_tax_tab_links_preserve_period_and_account(client, repo):
    """The three tab anchors (Wash sales / Projection / Performance) must
    include both `period=` and `account=` query params when the user is
    viewing a non-default scope."""
    repo.get_or_create_account("schwab", "personal")
    seed_import(
        repo,
        "schwab",
        "personal",
        [
            make_buy("schwab/personal", "SPY", date(2024, 1, 15), qty=10, cost=4000),
        ],
    )
    r = client.get("/tax?view=performance&period=2024&account=schwab/personal")
    assert r.status_code == 200
    body = r.text

    # Every tab anchor must carry both scope params.
    assert 'href="/tax?view=wash-sales' in body
    assert 'href="/tax?view=projection' in body
    assert 'href="/tax?view=performance' in body
    # period= shows up in each tab link.
    assert body.count("&period=2024") >= 3
    # account= round-trips with `/` preserved by Jinja's urlencode.
    assert body.count("&account=schwab/personal") >= 3


# ---- audit #28 — wash-sales lag-sort & reset drop account filter -----------


def test_wash_sales_lag_sort_url_preserves_account_and_period(client, repo):
    """The lag-sort header link inside _detail_table.html must include each
    `selected_accounts` entry (the template used to read `filter_account`
    singular) and the `selected_period`. Also asserts the link targets
    /tax directly (not /wash-sales, which 301s)."""
    _seed_wash_violations(repo)
    r = client.get(f"/tax?view=wash-sales&period={_YR}&account=schwab/personal")
    assert r.status_code == 200
    body = r.text

    # The lag-sort URL should target /tax and carry account + period.
    assert "sort=lag" in body
    # Find the lag link.
    import re

    lag_hrefs = re.findall(r'href="(/tax\?[^"]*sort=lag[^"]*)"', body)
    assert lag_hrefs, "lag-sort link not found in response"
    lag_href = lag_hrefs[0]
    assert "account=schwab/personal" in lag_href
    assert f"period={_YR}" in lag_href
    # Must NOT be the legacy /wash-sales path.
    assert not lag_href.startswith("/wash-sales")


def test_wash_sales_filter_reset_preserves_account_and_period(client, repo):
    """The ⌫ reset chip anchor (`data-testid="filter-reset"`) preserves
    `selected_accounts` and `selected_period`."""
    _seed_wash_violations(repo)
    r = client.get(f"/tax?view=wash-sales&period={_YR}&account=schwab/personal")
    assert r.status_code == 200
    body = r.text

    # Filter-chip reset anchor — must include account + period in its href.
    assert 'data-testid="filter-reset"' in body
    reset_lines = [line for line in body.splitlines() if 'data-testid="filter-reset"' in line]
    assert reset_lines, "filter-reset anchor not found"
    reset_href = reset_lines[0]
    assert "account=schwab/personal" in reset_href
    assert f"period={_YR}" in reset_href


# ---- audit #29 — at-loss "harvestable only" toggle drops scope -------------


def test_at_loss_harvestable_toggle_preserves_period_and_account(client, repo):
    """The `_positions_view_at_loss.html` HTMX form must include hidden
    `period` and `account` inputs so the toggle doesn't strip scope."""
    repo.get_or_create_account("schwab", "personal")
    seed_import(
        repo,
        "schwab",
        "personal",
        [
            # Open lot at a loss vs current price (no realized close yet).
            make_buy("schwab/personal", "TSLA", date(2024, 1, 5), qty=10, cost=2500),
        ],
    )
    r = client.get("/positions?view=at-loss&period=2024&account=schwab/personal")
    assert r.status_code == 200
    body = r.text

    # Hidden inputs for period + account must be present inside the form.
    assert '<input type="hidden" name="period" value="2024">' in body
    assert '<input type="hidden" name="account" value="schwab/personal">' in body
    # Form action defaults to /positions (audit #29 second bullet). The route
    # always sets harvest_form_action="/positions?view=at-loss", so we assert
    # the rendered hx-get carries the positions path — not the /tax fallback.
    assert 'hx-get="/positions?view=at-loss"' in body
