"""The multi-symbol filter on the Holdings toolbar must:
1. Render with no leaked Alpine expression text in the page body.
2. Reference the named Alpine component (symbolFilter) — not a 30-line inline x-data.
"""

from datetime import date

from fastapi.testclient import TestClient


def test_no_alpine_expression_text_leaks(client: TestClient, builders, repo):
    builders.seed_import(repo, "schwab", "lt", [
        builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5)),
    ])
    res = client.get("/portfolio/positions?period=ytd&account=&group_options=merge&show=open&page=1")
    assert res.status_code == 200
    # The body of the old x-data leaked these strings to the rendered page.
    # After extraction, only the call site `symbolFilter({...})` should appear.
    assert "this.selected.indexOf" not in res.text
    assert "this.all.filter" not in res.text
    # Function body definitions should not appear in page text (call sites like
    # x-for="s in filtered()" are fine — those are Alpine binding expressions).
    assert "filtered() {" not in res.text  # method definition body should not appear
    assert "return q ?" not in res.text    # inner logic should not appear
    # The Alpine component name should be present as the x-data value.
    assert "symbolFilter(" in res.text


def test_static_holdings_filter_js_served(client: TestClient):
    res = client.get("/static/holdings_filter.js")
    assert res.status_code == 200
    assert "Alpine.data" in res.text
    assert "symbolFilter" in res.text


def test_base_template_loads_holdings_filter_script(client: TestClient, builders, repo):
    res = client.get("/")
    assert res.status_code == 200
    assert "/static/holdings_filter.js" in res.text
