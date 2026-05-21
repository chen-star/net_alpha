"""Baseline security headers must be set on every response.

We bind loopback only, so the threat is "another tab in the same browser":
- Framing: a malicious page <iframe>s /tax to bait clicks against our DOM.
  X-Frame-Options + frame-ancestors close this off.
- MIME sniffing: a stored response masquerading as a different type.
  X-Content-Type-Options: nosniff disables IE/Edge sniffing.
- Referrer leakage: if the user clicks an outbound link, the destination
  shouldn't see our local URLs / query strings.
- Inline script discipline: CSP keeps src=self only for fetched assets,
  even though our inline <script>/<style> blocks require 'unsafe-inline'
  on script/style (HTMX + Alpine + per-chart inline render).
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_x_frame_options_deny_set(client: TestClient):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.headers.get("x-frame-options") == "DENY"


def test_x_content_type_options_nosniff_set(client: TestClient):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.headers.get("x-content-type-options") == "nosniff"


def test_referrer_policy_same_origin_set(client: TestClient):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.headers.get("referrer-policy") == "same-origin"


def test_csp_has_default_src_self_and_frame_ancestors_none(client: TestClient):
    """Frame-ancestors is the modern (and more reliable) replacement for
    X-Frame-Options; we set both for browser coverage."""
    resp = client.get("/")
    assert resp.status_code == 200
    csp = resp.headers.get("content-security-policy") or ""
    assert "default-src 'self'" in csp, csp
    assert "frame-ancestors 'none'" in csp, csp


def test_headers_apply_to_fragment_endpoints_too(client: TestClient):
    """HTMX fragment responses must carry the same headers — a clickjack
    against /portfolio/kpis is just as dangerous as against /."""
    resp = client.get("/portfolio/kpis")
    # Some fragments may 404 in a bare test DB; we just need a non-5xx
    # response to inspect headers.
    assert resp.status_code < 500
    assert resp.headers.get("x-frame-options") == "DENY"
    assert resp.headers.get("x-content-type-options") == "nosniff"
