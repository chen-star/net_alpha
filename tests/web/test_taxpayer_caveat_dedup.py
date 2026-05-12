"""B2: The taxpayer-level offset caveat renders exactly once per /tax page
view when an account filter is active."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient


def test_caveat_renders_once_on_tax_page_with_filter(client: TestClient, builders, repo):
    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5))],
    )
    res = client.get("/tax?account=schwab/lt")
    body = res.text
    count = body.count("Offset budget is taxpayer-level")
    assert count == 1, f"Expected caveat once, got {count}"


def test_caveat_omitted_when_no_filter(client: TestClient, builders, repo):
    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5))],
    )
    res = client.get("/tax")
    assert "Offset budget is taxpayer-level" not in res.text


def test_caveat_uses_data_testid(client: TestClient, builders, repo):
    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5))],
    )
    res = client.get("/tax?account=schwab/lt")
    assert 'data-testid="taxpayer-caveat"' in res.text
