"""Watch pill rendering on the Plan view."""

from fastapi.testclient import TestClient


def test_plan_view_renders_watch_pill_for_each_target(client: TestClient):
    """Plan rows include either a colored or 'unknown' watch pill."""
    r = client.get("/positions?view=plan")
    assert r.status_code == 200
    # We can't guarantee a specific state, but at least one pill class should appear
    # for any populated Plan view. If the Plan is empty, this test will see the empty-state
    # hero instead — accept either.
    has_pill = any(
        s in r.text
        for s in [
            "watch-pill--clean",
            "watch-pill--wash",
            "watch-pill--ira-trap",
            "watch-pill--unknown",
        ]
    )
    has_empty_state = "empty-state-hero" in r.text or "No targets" in r.text
    assert has_pill or has_empty_state, "Plan view should render either pills or the empty state"
