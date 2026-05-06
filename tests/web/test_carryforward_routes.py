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


def test_post_upsert_creates_override(client: TestClient, repo: Repository) -> None:
    resp = client.post(
        "/settings/carryforward/save",
        data={"year": "2025", "st_amount": "1500", "lt_amount": "300", "note": "from 2024 1040"},
    )
    assert resp.status_code == 200
    saved = repo.get_carryforward_override(2025)
    assert saved is not None
    assert saved.st_amount == Decimal("1500")
    assert saved.lt_amount == Decimal("300")
    assert saved.note == "from 2024 1040"


def test_post_upsert_overwrites_existing(client: TestClient, repo: Repository) -> None:
    repo.upsert_carryforward_override(year=2025, st=Decimal("1"), lt=Decimal("0"))
    client.post(
        "/settings/carryforward/save",
        data={"year": "2025", "st_amount": "999", "lt_amount": "0"},
    )
    saved = repo.get_carryforward_override(2025)
    assert saved is not None
    assert saved.st_amount == Decimal("999")


def test_post_reset_deletes_override(client: TestClient, repo: Repository) -> None:
    repo.upsert_carryforward_override(year=2025, st=Decimal("1500"), lt=Decimal("0"))
    resp = client.post("/settings/carryforward/reset?year=2025")
    assert resp.status_code == 200
    assert repo.get_carryforward_override(2025) is None


def test_post_rejects_negative_amounts(client: TestClient) -> None:
    resp = client.post(
        "/settings/carryforward/save",
        data={"year": "2025", "st_amount": "-100", "lt_amount": "0"},
    )
    assert resp.status_code == 422


def test_get_edit_returns_form_row(client: TestClient, repo: Repository) -> None:
    repo.upsert_carryforward_override(year=2025, st=Decimal("100"), lt=Decimal("50"))
    resp = client.get("/settings/carryforward/edit?year=2025")
    assert resp.status_code == 200
    assert 'name="st_amount"' in resp.text
    assert 'value="100' in resp.text
