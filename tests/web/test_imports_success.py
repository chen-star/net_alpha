from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def _fixture_csv() -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures" / "schwab_sample.csv"


def test_post_imports_redirects_to_success(client: TestClient) -> None:
    """After a successful commit, the route redirects to /imports/success?id=N."""
    with _fixture_csv().open("rb") as f:
        resp = client.post(
            "/imports",
            data={"account": "test"},
            files=[("files", ("schwab_sample.csv", f, "text/csv"))],
            follow_redirects=False,
        )
    assert resp.status_code in (302, 303, 307), f"unexpected status {resp.status_code}: {resp.text}"
    location = resp.headers["location"]
    assert "/imports/success" in location
    assert "id=" in location


def test_post_imports_blocked_in_demo_mode(client: TestClient) -> None:
    client.app.state.demo_mode = True
    try:
        with _fixture_csv().open("rb") as f:
            resp = client.post(
                "/imports",
                data={"account": "demo"},
                files={"files": ("schwab_sample.csv", f, "text/csv")},
                follow_redirects=False,
            )
        assert resp.status_code in (302, 303, 307)
        assert resp.headers["location"] == "/welcome"
    finally:
        client.app.state.demo_mode = False


def test_imports_success_renders_summary(client: TestClient) -> None:
    """The success page shows trade count and CTAs to /tax and /."""
    with _fixture_csv().open("rb") as f:
        post_resp = client.post(
            "/imports",
            data={"account": "test"},
            files=[("files", ("schwab_sample.csv", f, "text/csv"))],
            follow_redirects=False,
        )
    location = post_resp.headers["location"]
    assert "/imports/success" in location

    resp = client.get(location, follow_redirects=False)
    assert resp.status_code == 200, resp.text
    body = resp.text
    assert "Import complete" in body
    assert "/tax" in body
    assert 'href="/"' in body
