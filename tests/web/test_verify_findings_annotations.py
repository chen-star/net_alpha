"""Tests that verify-page findings render muted 'expected' badges when
detail annotations are set.

A BasisRecon finding can carry annotations on its ``detail`` dict:

  * ``expected_section_1256``  — Schwab's year-end §1256(a)(1) MTM diverges
    from our open-lot basis; the divergence is expected.
  * ``expected_cross_account`` — a §1091 wash-sale violation crosses
    accounts and Schwab's per-account CSV can't see the opposite leg.

Either flag should render a muted "expected · …" badge next to the scope
column. Severity classification is unchanged — this is purely UI polish.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from net_alpha.db.repository import Repository
from net_alpha.verify.invariants import InvariantResult
from net_alpha.verify.tolerances import Severity


def _seed_verify_run_with_annotated_finding(repo: Repository, *, detail: dict) -> int:
    """Insert a verify_result + one BasisRecon finding with the given detail."""
    f = InvariantResult(
        rule_id="BasisRecon",
        severity=Severity.WARN,
        scope="SPX/A",
        ours=4500.0,
        theirs=5000.0,
        delta=-500.0,
        detail=detail,
    )
    return repo.save_verify_run(
        run_at=datetime.now(UTC).isoformat(),
        trigger="manual",
        status="warn",
        duration_ms=0,
        checks_total=1,
        checks_passed=0,
        checks_warned=1,
        checks_failed=0,
        reference_age_days=0,
        notes="test",
        findings=[f],
    )


def test_findings_table_shows_section_1256_badge(client: TestClient, repo: Repository):
    _seed_verify_run_with_annotated_finding(
        repo,
        detail={"expected_section_1256": True, "expected_cross_account": False},
    )
    resp = client.get("/verify")
    assert resp.status_code == 200
    html = resp.text
    assert 'data-testid="expected-badge"' in html
    assert "1256" in html


def test_findings_table_shows_cross_account_badge(client: TestClient, repo: Repository):
    _seed_verify_run_with_annotated_finding(
        repo,
        detail={"expected_section_1256": False, "expected_cross_account": True},
    )
    resp = client.get("/verify")
    assert resp.status_code == 200
    html = resp.text
    assert 'data-testid="expected-badge"' in html
    assert "cross-account" in html.lower() or "cross account" in html.lower()


def test_findings_table_no_badge_when_no_annotations(client: TestClient, repo: Repository):
    _seed_verify_run_with_annotated_finding(repo, detail={})
    resp = client.get("/verify")
    assert resp.status_code == 200
    assert 'data-testid="expected-badge"' not in resp.text
