"""Phase 1 top-nav rewrite (§3.1 / §6.1 of UI/UX redesign spec)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_nav_has_four_top_level_links(client: TestClient):
    """Overview, Positions, Tax, Sim — Imports is no longer in the top nav."""
    resp = client.get("/")
    html = resp.text
    assert ">Overview<" in html
    assert ">Positions<" in html
    assert ">Tax<" in html
    assert ">Sim<" in html
    # Imports is moved to Settings drawer; should NOT be a top-nav link.
    # (href="/imports" may still appear in page body links like the empty-state CTA,
    # so we only assert it is absent from nav-link anchors.)
    assert 'class="nav-link' not in html or '/imports' not in [
        line.strip() for line in html.split('\n') if 'nav-link' in line and 'imports' in line.lower()
    ]


def test_nav_link_for_positions_points_to_slash_positions(client: TestClient):
    resp = client.get("/")
    assert 'href="/positions"' in resp.text


def test_nav_link_for_sim_points_to_slash_sim(client: TestClient):
    resp = client.get("/")
    assert 'href="/sim"' in resp.text


def test_nav_active_state_on_overview(client: TestClient):
    resp = client.get("/")
    html = resp.text
    overview_idx = html.find(">Overview<")
    assert overview_idx > 0
    anchor_start = html.rfind("<a", 0, overview_idx)
    anchor_html = html[anchor_start:overview_idx]
    assert "active" in anchor_html, f"Overview link missing active class: {anchor_html}"


def test_nav_active_state_on_positions(client: TestClient):
    resp = client.get("/positions")
    html = resp.text
    pos_idx = html.find(">Positions<")
    assert pos_idx > 0
    anchor_start = html.rfind("<a", 0, pos_idx)
    anchor_html = html[anchor_start:pos_idx]
    assert "active" in anchor_html


def test_old_imports_nav_badge_no_longer_appears_in_topbar_links(client: TestClient):
    """The yellow badge that used to live on the Imports nav link is gone."""
    resp = client.get("/")
    assert 'data-testid="imports-badge"' not in resp.text or '"/imports"' not in resp.text


def test_topbar_no_redundant_period_or_account_pills(client: TestClient):
    """The Period and Account pills duplicate the page subhead and are
    removed in Phase 1 (audit P10)."""
    resp = client.get("/")
    html = resp.text
    assert 'class="pill"' not in html, "found leftover topbar pill"


@pytest.mark.parametrize(
    "label,path",
    [
        ("Overview", "/"),
        ("Positions", "/positions"),
        ("Tax", "/tax"),
        ("Sim", "/sim"),
    ],
)
def test_nav_link_round_trip(client: TestClient, label: str, path: str):
    home = client.get("/")
    assert f'href="{path}"' in home.text, f"{label} link missing from /"
    page = client.get(path)
    assert page.status_code == 200, f"{label} → {path} returned {page.status_code}"
    assert f">{label}<" in page.text, f"{label} link missing from {path}"
