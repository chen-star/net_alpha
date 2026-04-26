from __future__ import annotations


def test_404_renders_error_page(client):
    resp = client.get("/this-route-does-not-exist")
    assert resp.status_code == 404
    assert "Not found" in resp.text or "404" in resp.text


def test_500_handler_renders_error_page(client):
    resp = client.get("/__test_500__")
    assert resp.status_code == 500
    assert "Server error" in resp.text or "500" in resp.text
