"""The shared period/account toolbar must POST back to the page that rendered it,
not always to /. Otherwise changing Account on /holdings bounces to /."""

from fastapi.testclient import TestClient


def test_toolbar_form_action_on_portfolio_page(client: TestClient, builders, repo):
    from datetime import date

    builders.seed_import(repo, "schwab", "lt", [builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5))])
    res = client.get("/")
    assert res.status_code == 200
    assert 'action="/"' in res.text


def test_toolbar_form_action_on_holdings_page(client: TestClient, builders, repo):
    from datetime import date

    builders.seed_import(repo, "schwab", "lt", [builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5))])
    res = client.get("/holdings")
    assert res.status_code == 200
    assert 'action="/holdings"' in res.text
    assert 'action="/"' not in res.text
