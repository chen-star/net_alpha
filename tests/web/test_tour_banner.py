from __future__ import annotations

from fastapi.testclient import TestClient


def test_no_banner_without_tour_query(client: TestClient) -> None:
    resp = client.get("/welcome")
    assert b"data-tour-banner" not in resp.content


def test_banner_step_one_renders_wash_sale_copy(client_with_data: TestClient) -> None:
    resp = client_with_data.get("/?tour=1")
    assert resp.status_code == 200
    assert b"data-tour-banner" in resp.content
    assert b"Step 1 of 3" in resp.content
    assert b"wash sale" in resp.content.lower()


def test_banner_step_two_renders_tax_copy(client_with_data: TestClient) -> None:
    resp = client_with_data.get("/tax?tour=2")
    assert resp.status_code == 200
    assert b"Step 2 of 3" in resp.content
    assert b"tax" in resp.content.lower()


def test_banner_step_three_renders_portfolio_copy(client_with_data: TestClient) -> None:
    resp = client_with_data.get("/?tour=3")
    assert resp.status_code == 200
    assert b"Step 3 of 3" in resp.content


def test_banner_done_step_shows_replay_and_exit(client_with_data: TestClient) -> None:
    resp = client_with_data.get("/?tour=done")
    assert resp.status_code == 200
    assert b"Replay tour" in resp.content
    assert b"Switch to my data" in resp.content


def test_no_banner_on_welcome_even_with_tour_query(client: TestClient) -> None:
    resp = client.get("/welcome?tour=1")
    assert resp.status_code == 200
    assert b"data-tour-banner" not in resp.content
