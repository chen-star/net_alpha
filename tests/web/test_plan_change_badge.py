"""Plan-view change badge: rendered when change_states[symbol] is non-null."""

from __future__ import annotations

from decimal import Decimal

from net_alpha.targets.models import TargetUnit


def _seed_target(repo, *, symbol: str = "NVDA"):
    """Seed one PositionTarget. Uses Repository.upsert_target."""
    repo.upsert_target(symbol, Decimal("10"), TargetUnit.SHARES)


def test_first_visit_badges_every_row_as_new(client, repo):
    """First-ever Plan-view render with empty snapshot: at least one 'new'
    badge appears."""
    _seed_target(repo, symbol="NVDA")
    resp = client.get("/positions?view=plan")
    assert resp.status_code == 200
    assert 'data-change-state="new"' in resp.text


def test_mark_as_seen_clears_badges(client, repo):
    """After POST /positions/plan/mark-seen, badges no longer render.
    Note: this test depends on the Task 12 route handler. Until Task 12 lands,
    this test will fail with 404 on the POST, which is expected."""
    _seed_target(repo, symbol="NVDA")
    client.get("/positions?view=plan")  # ensure rows are rendered once
    resp = client.post("/positions/plan/mark-seen")
    assert resp.status_code in (200, 204), resp.status_code
    later = client.get("/positions?view=plan")
    assert 'data-change-state="new"' not in later.text
    assert 'data-change-state="changed"' not in later.text


def test_mark_as_seen_button_is_present(client):
    resp = client.get("/positions?view=plan")
    assert resp.status_code == 200
    # Either label is acceptable; pick whichever Task 11 uses.
    assert "Mark as seen" in resp.text or "Mark all seen" in resp.text
