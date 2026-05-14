"""A3: Skeleton loaders appear in the four HTMX lazy-load slots."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient


def test_portfolio_body_skeleton_renders_initially(client: TestClient, builders, repo):
    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5))],
    )
    res = client.get("/")
    body = res.text
    # Skeleton inside #portfolio-body so it paints before the lazy load returns.
    assert 'data-skeleton="kpi-row"' in body or 'class="skeleton' in body


def test_verify_badge_slot_removed_from_overview(client: TestClient, builders, repo):
    """The page-level verify badge slot was removed from /. The topbar
    "Data check: …" pill (base.html) now surfaces the same status, so the
    slot's skeleton is no longer rendered."""
    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5))],
    )
    res = client.get("/")
    body = res.text
    assert 'class="verify-badge-slot"' not in body


def test_positions_pane_has_skeleton(client: TestClient, builders, repo):
    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5))],
    )
    res = client.get("/positions")
    body = res.text
    assert "skeleton" in body  # appears at least somewhere
