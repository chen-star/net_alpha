"""Plan-view change badge — server attaches change_states keyed by symbol."""

from __future__ import annotations


def test_plan_view_renders_without_error_when_snapshot_empty(client):
    """First-ever render: snapshot is empty, every row's change_state should
    end up "new". Smoke that nothing crashes and the template still renders."""
    resp = client.get("/positions?view=plan")
    assert resp.status_code == 200
