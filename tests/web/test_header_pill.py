"""Phase 6 / Task 20: global header verify-status pill.

The pill renders in the topbar of every page (via base.html) and summarises
the latest verify run status. With no runs it renders 'grey'; otherwise the
latest run's status string is reused as the pill modifier.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_header_pill_renders_grey_when_no_runs(client: TestClient):
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'data-verify-pill="grey"' in resp.text


def test_header_pill_links_to_verify(client: TestClient):
    resp = client.get("/")
    assert resp.status_code == 200
    # The pill is an anchor that takes the user to the /verify page.
    assert 'href="/verify"' in resp.text


def test_header_pill_renders_on_positions(client: TestClient):
    resp = client.get("/positions")
    assert resp.status_code == 200
    assert "data-verify-pill=" in resp.text


def test_header_pill_renders_on_tax(client: TestClient):
    resp = client.get("/tax")
    assert resp.status_code == 200
    assert "data-verify-pill=" in resp.text
