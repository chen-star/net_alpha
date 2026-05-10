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


def test_mark_as_seen_persists_timestamp_and_snapshot(client, repo):
    """Posting mark-seen writes plan_last_seen_at and rewrites the snapshot."""
    _seed_target(repo, symbol="NVDA")
    assert repo.get_plan_last_seen_at() is None
    resp = client.post("/positions/plan/mark-seen")
    assert resp.status_code in (200, 204)
    assert repo.get_plan_last_seen_at() is not None
    snap = repo.read_plan_snapshot()
    assert "NVDA" in snap


def test_mark_as_seen_snapshot_is_global_not_account_filtered(client, repo):
    """Posting mark-seen with ?account=… must NOT filter the snapshot — the
    snapshot is always cross-account global. Otherwise pl_bucket entries for
    out-of-account targets would silently snapshot as 0, corrupting future
    diffs after the user switches back to All accounts."""
    _seed_target(repo, symbol="NVDA")
    # POST with an account filter — the snapshot must still cover NVDA.
    resp = client.post("/positions/plan/mark-seen?account=fake/none")
    assert resp.status_code in (200, 204), resp.status_code
    snap = repo.read_plan_snapshot()
    assert "NVDA" in snap, (
        "snapshot must include all targets regardless of account filter "
        "on the request URL — otherwise multi-account users get corrupted "
        "snapshots when marking as seen from a filtered view"
    )
