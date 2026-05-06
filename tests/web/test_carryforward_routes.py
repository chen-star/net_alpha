"""GET /settings/carryforward — list per-year carryforward state.

Read-only fragment shown inside the Settings drawer. Lists each tax year
with its derived (from history) or override-sourced ST/LT magnitudes.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from net_alpha.db.repository import Repository


def test_settings_carryforward_section_renders_for_empty_db(client: TestClient) -> None:
    resp = client.get("/settings/carryforward")
    assert resp.status_code == 200
    body = resp.text
    assert "Loss carryforwards" in body
    assert "no prior-year history" in body.lower()


def test_settings_carryforward_section_shows_override_row(client: TestClient, repo: Repository) -> None:
    repo.upsert_carryforward_override(year=2025, st=Decimal("1234"), lt=Decimal("0"))
    resp = client.get("/settings/carryforward")
    assert resp.status_code == 200
    body = resp.text
    assert "2025" in body
    assert "1,234" in body or "1234" in body
    # Override-sourced row is labeled as such.
    assert "from override" in body.lower() or "user" in body.lower()
