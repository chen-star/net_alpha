from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def test_welcome_renders_when_db_empty(client: TestClient) -> None:
    resp = client.get("/welcome", follow_redirects=False)
    assert resp.status_code == 200
    assert b"Take a 30-second tour" in resp.content
    assert b"Import my CSV" in resp.content


def test_welcome_redirects_when_user_has_imports(client_with_data: TestClient) -> None:
    resp = client_with_data.get("/welcome", follow_redirects=False)
    assert resp.status_code in (302, 303, 307)
    assert resp.headers["location"] == "/"


def test_welcome_replay_query_renders_even_with_data(client_with_data: TestClient) -> None:
    resp = client_with_data.get("/welcome?replay=1", follow_redirects=False)
    assert resp.status_code == 200


def test_start_tour_builds_demo_db_and_flips_mode(client: TestClient, tmp_data_dir: Path) -> None:
    resp = client.post("/welcome/start-tour", follow_redirects=False)
    assert resp.status_code in (302, 303, 307)
    assert resp.headers["location"] == "/?tour=1"
    assert (tmp_data_dir / "demo.db").exists()
    assert client.app.state.demo_mode is True


def test_start_import_redirects_to_imports(client: TestClient) -> None:
    resp = client.post("/welcome/start-import", follow_redirects=False)
    assert resp.status_code in (302, 303, 307)
    assert resp.headers["location"] == "/imports"
