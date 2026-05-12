"""Phase 6 / Task 19: /verify page + /verify/run + /verify/findings/{id}.

The /verify/badge HTMX fragment was added in Task 10 — these new routes
live alongside it in the same verify router (web/routes/verify.py).
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_verify_page_renders(client: TestClient):
    resp = client.get("/verify")
    assert resp.status_code == 200
    assert "Verification" in resp.text


def test_verify_run_post_triggers_a_run(client: TestClient):
    resp = client.post("/verify/run", follow_redirects=False)
    # 303 See Other on success (redirect to /verify); 200 also acceptable
    # if a future change renders the result page directly.
    assert resp.status_code in (200, 303)


def test_verify_findings_endpoint_returns_404_for_unknown_run(client: TestClient):
    resp = client.get("/verify/findings/999999")
    assert resp.status_code == 404
