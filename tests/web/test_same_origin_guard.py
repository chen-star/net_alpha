"""Cross-origin POST/PUT/PATCH/DELETE must be blocked by the middleware.

Threat model: the user opens net-alpha at http://127.0.0.1:18765 in tab A,
then visits a malicious page in tab B that fires `fetch('http://127.0.0.1:18765/quit', {method: 'POST'})`.
The fetch carries Origin: <evil-domain>. The middleware compares that against
the request's own Host (127.0.0.1) — different host → 403.

Local CLI tools (curl, httpie) that don't set Origin/Referer continue to work.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_same_origin_post_allowed(client: TestClient):
    """A POST from TestClient's default referer (testserver) must pass —
    same host as the implicit Host header set by TestClient."""
    resp = client.post(
        "/tour/dismiss",
        headers={"referer": "http://testserver/?tour=1"},
        follow_redirects=False,
    )
    assert resp.status_code != 403, "same-origin POST should not be blocked"


def test_cross_origin_post_blocked_via_referer(client: TestClient):
    """POST with Referer pointing at a different host gets a 403."""
    resp = client.post(
        "/tour/dismiss",
        headers={"referer": "https://evil.example.com/attack"},
        follow_redirects=False,
    )
    assert resp.status_code == 403
    assert "cross-origin" in resp.text.lower()


def test_cross_origin_post_blocked_via_origin(client: TestClient):
    """POST with Origin pointing at a different host gets a 403, even if
    Referer is absent. fetch() in modern browsers always sets Origin for
    cross-origin mutating requests."""
    resp = client.post(
        "/tour/dismiss",
        headers={"origin": "https://evil.example.com"},
        follow_redirects=False,
    )
    assert resp.status_code == 403


def test_get_request_with_foreign_referer_not_blocked(client: TestClient):
    """Read-only requests aren't gated — they can't mutate state."""
    resp = client.get(
        "/",
        headers={"referer": "https://evil.example.com/attack"},
    )
    assert resp.status_code != 403


def test_post_with_no_origin_or_referer_not_blocked(client: TestClient):
    """CLI tools (curl, httpie) typically send neither header. The middleware
    allows that path so the user's own scripts keep working."""
    resp = client.post("/tour/dismiss", follow_redirects=False)
    assert resp.status_code != 403
