"""`POST /settings/carryforward/reset` must accept ``year`` from the form body
(audit #20).

Before the fix, ``year`` was a query parameter — submitting a form-encoded
``year=2024`` body produced a 422. The fix declares ``year`` as
``Form(...)`` so the form-encoded body is the canonical input. Backwards
compatibility for the existing hx-post template (which carries the year in
the query string) is preserved by the route's existing ``Request``-based
fallback / FastAPI's tolerance of either origin when both work.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from net_alpha.db.repository import Repository


def test_reset_accepts_form_body_year(client: TestClient, repo: Repository) -> None:
    """Form-encoded ``year=2024`` in the body, no query string, succeeds and
    deletes the override."""
    repo.upsert_carryforward_override(year=2024, st=Decimal("750"), lt=Decimal("0"))
    resp = client.post(
        "/settings/carryforward/reset",
        data={"year": "2024"},
    )
    assert resp.status_code == 200, resp.text
    assert repo.get_carryforward_override(2024) is None


def test_reset_template_submits_year_in_form_body(client: TestClient, repo: Repository) -> None:
    """The carryforward template must POST ``year`` as a form value so it
    matches the ``Form(...)``-typed handler — either via a hidden input or
    via ``hx-vals``."""
    repo.upsert_carryforward_override(year=2025, st=Decimal("1500"), lt=Decimal("0"))
    resp = client.get("/settings/carryforward")
    assert resp.status_code == 200
    body = resp.text
    # The Reset button must carry the year through the form mechanism — either
    # as a hidden input (preferred) or as hx-vals — not just a query-string
    # path on hx-post.
    has_hidden_input = '<input type="hidden" name="year"' in body
    has_hx_vals_year = "hx-vals" in body and '"year"' in body
    assert has_hidden_input or has_hx_vals_year, (
        "Reset button must submit year via form body or hx-vals; only had query-string."
    )
