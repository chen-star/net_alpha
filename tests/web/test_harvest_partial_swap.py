"""A2.3: Harvest plan splits into #harvest-summary + #harvest-table.
Checkbox toggles target #harvest-summary; per-row tax-saved cells get
stable IDs for OOB swap; the route branches on HX-Target to return only
the summary partial + OOB cell fragments."""

from __future__ import annotations

import datetime as dt
from datetime import date, datetime
from decimal import Decimal

from fastapi.testclient import TestClient

from net_alpha.engine.etf_pairs import load_etf_pairs
from net_alpha.engine.recompute import recompute_all_violations
from net_alpha.engine.stitch import stitch_account
from net_alpha.pricing.cache import PriceCache
from net_alpha.pricing.provider import Quote


def _seed_loss(builders, repo):
    """Seed a single open buy and leave it without quotes.

    Sufficient for the structural assertions (region split, checkbox target,
    HTMX summary-only response) — the harvest queue can be empty for those.
    """
    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [
            builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5), qty=10, cost=1000),
        ],
    )


def _seed_harvest_row(builders, repo, engine):
    """Seed a buy + materialize lots + write a current quote BELOW basis so
    ``compute_harvest_queue`` actually produces a row.

    Mirrors the e2e fixture in ``tests/web/e2e/test_flow_clarity_e2e.py``:
    ``add_import`` only writes the trade table; lot rows are materialized
    by the wash-sale engine's ``detect_in_window`` pass (called via
    ``recompute_all_violations``).
    """
    buy_day = date.today() - dt.timedelta(days=45)
    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [
            builders.make_buy("schwab/lt", "AAPL", buy_day, qty=10, cost=1800),
        ],
    )
    for account in repo.list_accounts():
        stitch_account(repo, account.id)
    recompute_all_violations(repo, load_etf_pairs(user_path=None))
    # Quote at $90/share — well below $180 basis — to make the lot at a loss.
    cache = PriceCache(engine)
    cache.put_many([Quote(symbol="AAPL", price=Decimal("90.00"), as_of=datetime.now(dt.UTC), source="test")])


def test_harvest_regions_split(client: TestClient, builders, repo):
    _seed_loss(builders, repo)
    res = client.get("/tax/harvest/plan", headers={"HX-Request": "true"})
    body = res.text
    assert 'id="harvest-summary"' in body
    assert 'id="harvest-table"' in body


def test_checkbox_targets_summary_not_full_region(client: TestClient, builders, repo, engine):
    # Need a populated table for the checkbox row to render at all.
    _seed_harvest_row(builders, repo, engine)
    res = client.get("/tax/harvest/plan", headers={"HX-Request": "true"})
    body = res.text
    # Checkbox input now targets #harvest-summary, not the wrapping region.
    assert 'hx-target="#harvest-summary"' in body


def test_tax_saved_cells_have_stable_ids(client: TestClient, builders, repo, engine):
    """Tighten the previously-vacuous test: seed an actual harvest row so the
    assertion fires against a populated table."""
    _seed_harvest_row(builders, repo, engine)
    res = client.get("/tax/harvest/plan", headers={"HX-Request": "true"})
    body = res.text
    # Row must exist with the stable per-row id.
    assert "<tr data-symbol=" in body, "harvest fixture did not produce a row"
    assert 'id="tax-saved-AAPL-schwab_lt"' in body, (
        f"expected stable cell id 'tax-saved-AAPL-schwab_lt' in body; "
        f"got first 200 chars after data-symbol: "
        f"{body[body.index('data-symbol') : body.index('data-symbol') + 200]}"
    )


def test_htmx_summary_request_returns_only_summary(client: TestClient, builders, repo):
    _seed_loss(builders, repo)
    res = client.get(
        "/tax/harvest/plan?pick=AAPL::schwab/lt&mode=manual",
        headers={"HX-Request": "true", "HX-Target": "harvest-summary"},
    )
    body = res.text
    assert 'id="harvest-summary"' in body
    assert 'id="harvest-table"' not in body
