from __future__ import annotations

from fastapi.testclient import TestClient

from net_alpha.db.repository import Repository


def test_dismiss_marks_completed_and_redirects(client: TestClient, repo_real: Repository) -> None:
    resp = client.post("/tour/dismiss", headers={"referer": "http://testserver/?tour=1"}, follow_redirects=False)
    assert resp.status_code == 303
    assert repo_real.get_tour_completed() is True


def test_dismiss_strips_tour_query_from_referer(client: TestClient) -> None:
    resp = client.post("/tour/dismiss", headers={"referer": "http://testserver/tax?tour=2"}, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/tax"


def test_dismiss_with_no_referer_redirects_to_root(client: TestClient) -> None:
    resp = client.post("/tour/dismiss", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"


def test_replay_clears_completed_and_sets_demo_mode(client: TestClient, repo_real: Repository) -> None:
    repo_real.set_tour_completed(True)
    resp = client.post("/tour/replay", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/welcome?replay=1"
    assert client.app.state.demo_mode is True
    assert repo_real.get_tour_completed() is False


def test_exit_to_real_clears_demo_mode_and_marks_completed(client: TestClient, repo_real: Repository) -> None:
    client.app.state.demo_mode = True
    resp = client.post("/tour/exit-to-real", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/imports"
    assert client.app.state.demo_mode is False
    assert repo_real.get_tour_completed() is True


def test_settings_about_tab_has_replay_tour_form(client_with_data: TestClient) -> None:
    """The About tab in Settings should expose a replay-tour form."""
    resp = client_with_data.get("/settings?tab=about")
    assert resp.status_code == 200, resp.text
    body = resp.text
    assert 'action="/tour/replay"' in body
    assert "Replay onboarding tour" in body
    # audit #31 — button must use theme-aware tokens, not light-only
    # `border-slate-300` / `hover:bg-slate-50` (which render almost invisibly
    # against the dark canvas the user defaults to).
    assert "border-slate-300" not in body
    assert "hover:bg-slate-50" not in body
    assert "border-hairline" in body
    assert "hover:bg-surface-2" in body
