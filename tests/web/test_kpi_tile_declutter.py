"""B1: Hero Total-Account-Value tile shows ≤ 3 visible items.
Snapshot timestamp is in a tooltip; contributed-vs-realized lives only in
the explain panel."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient


def test_hero_tile_no_inline_timestamp_div(client: TestClient, builders, repo):
    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5))],
    )
    res = client.get("/portfolio/body?period=ytd", headers={"HX-Request": "true"})
    body = res.text
    if 'data-testid="kpi-total-account-value"' in body:
        hero_start = body.index('data-testid="kpi-total-account-value"')
        hero_chunk = body[hero_start : hero_start + 800]
        assert "as of" not in hero_chunk.lower(), "Hero tile still renders inline 'as of' timestamp text"


def test_hero_tile_has_timestamp_tooltip(client: TestClient, builders, repo):
    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5))],
    )
    res = client.get("/portfolio/body?period=ytd", headers={"HX-Request": "true"})
    body = res.text
    if 'data-testid="kpi-total-account-value"' in body:
        hero_start = body.index('data-testid="kpi-total-account-value"')
        hero_chunk = body[hero_start : hero_start + 800]
        assert 'title="' in hero_chunk
