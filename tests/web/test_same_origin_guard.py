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


def test_origin_null_is_blocked(client: TestClient):
    """`Origin: null` is what browsers send from sandboxed iframes / file://
    pages — refuse those rather than silently passing past the same-host
    comparison (urlparse('null').hostname is None)."""
    resp = client.post(
        "/tour/dismiss",
        headers={"origin": "null"},
        follow_redirects=False,
    )
    assert resp.status_code == 403


def test_dns_rebinding_blocked_by_host_allowlist(client: TestClient):
    """DNS rebinding: attacker registers evil.example.com → 127.0.0.1, lures
    the victim to a page on evil.example.com that, after the DNS TTL flips,
    fetches http://evil.example.com:18765/quit. The browser sends both
    Host: evil.example.com AND Origin: http://evil.example.com — strings
    match, so the bare same-origin equality check would pass.

    The fix: reject any mutating request whose Host header is not one of
    the loopback names the server is actually meant to answer on. That
    Host allowlist closes the rebinding window even when Origin lines up.
    """
    resp = client.post(
        "/tour/dismiss",
        headers={
            "host": "evil.example.com",
            "origin": "http://evil.example.com",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 403
    assert "host" in resp.text.lower()


def test_dns_rebinding_blocked_when_host_changed_but_origin_loopback(
    client: TestClient,
):
    """Even if the browser-attached Origin somehow says 127.0.0.1, a Host
    header that points elsewhere must still block. Defense in depth: the
    allowlist gates on Host alone so a single misset header can't defeat it.
    """
    resp = client.post(
        "/tour/dismiss",
        headers={
            "host": "evil.example.com",
            "origin": "http://127.0.0.1:18765",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 403


def _app_for_host(tmp_path, public_host: str | None):
    """Build a fresh app + client whose requests carry Host=public_host."""
    import os

    from net_alpha.config import Settings
    from net_alpha.db.connection import get_engine, init_db
    from net_alpha.web.app import create_app

    if public_host is None:
        os.environ.pop("NETALPHA_PUBLIC_HOST", None)
    else:
        os.environ["NETALPHA_PUBLIC_HOST"] = public_host
    os.environ["NETALPHA_SKIP_SCHEDULER"] = "1"
    settings = Settings(data_dir=tmp_path)
    init_db(get_engine(settings.db_path))
    app = create_app(settings)
    base = f"https://{public_host}" if public_host else "https://example.test"
    return TestClient(app, base_url=base, raise_server_exceptions=False)


def test_public_host_mutation_allowed_when_configured(tmp_path):
    """With NETALPHA_PUBLIC_HOST set, a same-host mutation from that domain passes."""
    client = _app_for_host(tmp_path, "net-alpha.example.com")
    try:
        resp = client.post(
            "/tour/dismiss",
            headers={"origin": "https://net-alpha.example.com"},
            follow_redirects=False,
        )
        assert resp.status_code != 403
    finally:
        import os

        os.environ.pop("NETALPHA_PUBLIC_HOST", None)


def test_public_host_rejected_when_not_configured(tmp_path):
    """Without the env var, that same domain is still an untrusted host → 403."""
    client = _app_for_host(tmp_path, None)
    resp = client.post(
        "/tour/dismiss",
        headers={"origin": "https://example.test"},
        follow_redirects=False,
    )
    assert resp.status_code == 403
