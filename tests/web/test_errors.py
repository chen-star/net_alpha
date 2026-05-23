from __future__ import annotations


def test_404_renders_error_page(client):
    resp = client.get("/this-route-does-not-exist")
    assert resp.status_code == 404
    assert "Not found" in resp.text or "404" in resp.text


def test_500_handler_renders_error_page(client):
    resp = client.get("/__test_500__")
    assert resp.status_code == 500
    assert "Server error" in resp.text or "500" in resp.text


def test_error_page_does_not_reuse_confidence_color(client):
    """audit #33 — the HTTP-status numeral must not borrow `.text-confirmed`
    (the wash-sale Confirmed tier color). It uses generic `.text-neg`."""
    resp = client.get("/this-route-does-not-exist")
    assert resp.status_code == 404
    body = resp.text
    # The status numeral lives in a div with class="text-... font-mono ... num".
    # Pin both the negative case (no Confirmed-tier leak) and the positive
    # case (generic text-neg is in play).
    assert "text-confirmed" not in body
    assert "text-neg" in body
