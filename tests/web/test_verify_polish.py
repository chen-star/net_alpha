"""UX polish on the /verify surface.

Covers the three deliverables added on top of the verify engine merge:
  * inline "Why?" explainer that maps rule_id -> guidance text
  * per-row Suppress action that mutates ~/.net_alpha/config.yaml
  * broker positions freshness banner / global pill suffix
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from net_alpha.db.repository import Repository
from net_alpha.verify.invariants import InvariantResult
from net_alpha.verify.suppress import _config_path, add_suppression, load_suppressions
from net_alpha.verify.tolerances import Severity

# --- helpers ----------------------------------------------------------------


def _seed_run_with_findings(repo: Repository, findings: list[InvariantResult]) -> int:
    """Persist one verify_result + the given findings; return the result id."""
    return repo.save_verify_run(
        run_at=datetime.now(UTC).isoformat(),
        trigger="manual",
        status="warn",
        duration_ms=10,
        checks_total=len(findings),
        checks_passed=0,
        checks_warned=sum(1 for f in findings if f.severity == Severity.WARN),
        checks_failed=sum(1 for f in findings if f.severity == Severity.FAIL),
        reference_age_days=None,
        notes="seeded",
        findings=findings,
    )


def _seed_basis_finding(repo: Repository) -> int:
    """Seed one BasisRecon finding and return its id."""
    _seed_run_with_findings(
        repo,
        [
            InvariantResult(
                rule_id="BasisRecon",
                severity=Severity.FAIL,
                scope="AAPL/Schwab-Taxable",
                ours=10_000.0,
                theirs=9_500.0,
                delta=500.0,
            )
        ],
    )
    latest = repo.latest_verify_run()
    findings = repo.list_verify_findings(run_id=latest.id)
    assert findings, "seeded finding should be persisted"
    return findings[0].id


# --- explain expander -------------------------------------------------------


def test_findings_table_renders_explain_toggle(client: TestClient, repo: Repository):
    """Every finding gets a Why? button + rule-specific guidance copy."""
    _seed_basis_finding(repo)
    html = client.get("/verify").text

    # The toggle is present.
    assert 'data-testid="verify-explain-toggle"' in html
    assert ">Why?<" in html

    # Rule-specific copy for BasisRecon is rendered.
    assert "Aggregate cost basis" in html
    # The deep link to per-ticker reconciliation uses the ticker stem
    # (before the slash) — verifies the template parses f.scope correctly.
    assert "/reconciliation/AAPL" not in html  # BasisRecon's copy doesn't link there
    assert "spinoffs, partial" in html  # the BasisRecon guidance paragraph


def test_findings_table_explain_handles_unknown_rule(client: TestClient, repo: Repository):
    """An unrecognized rule_id falls through to a generic explainer."""
    _seed_run_with_findings(
        repo,
        [
            InvariantResult(
                rule_id="MysteryRule",
                severity=Severity.WARN,
                scope="global",
                ours=1.0,
                theirs=2.0,
                delta=-1.0,
            )
        ],
    )
    html = client.get("/verify").text
    assert "MysteryRule" in html
    assert "No specific guidance is wired up yet" in html


# --- suppression ------------------------------------------------------------


def test_add_suppression_writes_yaml(tmp_path: Path, monkeypatch):
    """add_suppression() creates the config file if missing and writes a list."""
    monkeypatch.setenv("NET_ALPHA_DIR", str(tmp_path))
    add_suppression(
        rule_id="BasisRecon",
        scope="AAPL/Schwab-Taxable",
        reason="spinoff handled differently",
        until=date.today() + timedelta(days=365),
    )
    cfg_path = _config_path()
    assert cfg_path.exists()
    cfg = yaml.safe_load(cfg_path.read_text())
    assert cfg["verify"]["suppress"][0]["rule_id"] == "BasisRecon"
    assert cfg["verify"]["suppress"][0]["scope"] == "AAPL/Schwab-Taxable"
    assert cfg["verify"]["suppress"][0]["reason"] == "spinoff handled differently"


def test_add_suppression_is_idempotent(tmp_path: Path, monkeypatch):
    """Two adds with the same (rule_id, scope) update in place, no duplicates."""
    monkeypatch.setenv("NET_ALPHA_DIR", str(tmp_path))
    until1 = date(2030, 1, 1)
    until2 = date(2031, 1, 1)
    add_suppression(rule_id="OV-1", scope="global", reason="first", until=until1)
    add_suppression(rule_id="OV-1", scope="global", reason="second", until=until2)

    rules = load_suppressions()
    matching = [r for r in rules if r.rule_id == "OV-1" and r.scope == "global"]
    assert len(matching) == 1
    assert matching[0].reason == "second"
    assert matching[0].until == until2


def test_add_suppression_preserves_other_keys(tmp_path: Path, monkeypatch):
    """Hand-edited keys outside verify.suppress survive a suppress write."""
    monkeypatch.setenv("NET_ALPHA_DIR", str(tmp_path))
    cfg_path = _config_path()
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(
        yaml.safe_dump(
            {
                "pricing": {"enable_remote": False},
                "verify": {"tolerances": {"realized": {"abs": 1.0}}},
            }
        )
    )
    add_suppression(
        rule_id="OV-1",
        scope="global",
        reason="test",
        until=date(2030, 1, 1),
    )
    cfg = yaml.safe_load(cfg_path.read_text())
    assert cfg["pricing"]["enable_remote"] is False
    assert cfg["verify"]["tolerances"]["realized"]["abs"] == 1.0
    assert cfg["verify"]["suppress"][0]["rule_id"] == "OV-1"


def test_suppress_endpoint_writes_yaml_and_reruns(client: TestClient, repo: Repository, tmp_path: Path, monkeypatch):
    """POST /verify/findings/{id}/suppress writes YAML and 303-redirects."""
    monkeypatch.setenv("NET_ALPHA_DIR", str(tmp_path))
    finding_id = _seed_basis_finding(repo)

    resp = client.post(
        f"/verify/findings/{finding_id}/suppress",
        data={"reason": "tested suppression"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/verify"

    cfg = yaml.safe_load(_config_path().read_text())
    entry = cfg["verify"]["suppress"][0]
    assert entry["rule_id"] == "BasisRecon"
    assert entry["scope"] == "AAPL/Schwab-Taxable"
    assert entry["reason"] == "tested suppression"


def test_suppress_endpoint_404_on_missing_finding(client: TestClient):
    resp = client.post("/verify/findings/999999/suppress", data={"reason": "x"})
    assert resp.status_code == 404


# --- freshness banner -------------------------------------------------------


def test_freshness_banner_appears_when_no_positions_csv(client: TestClient):
    """With no broker_position rows the banner prompts the user to upload."""
    html = client.get("/verify").text
    assert 'data-testid="verify-freshness-banner"' in html
    assert "No broker All-Positions CSV has been uploaded yet" in html


def test_freshness_banner_marks_stale_when_old(client: TestClient, repo: Repository):
    """Banner severity flips to stale when the reference is older than 30 days."""
    stale_as_of = (date.today() - timedelta(days=45)).isoformat()
    repo.save_broker_positions(
        rows=[
            {
                "account_label": "Schwab/Taxable",
                "symbol": "AAPL",
                "qty": 10,
                "cost_basis": 1000,
                "market_value": 1500,
                "unrealized_pl": 500,
            }
        ],
        as_of_date=stale_as_of,
    )
    html = client.get("/verify").text
    assert 'data-freshness-severity="stale"' in html
    assert "45 days old" in html


def test_freshness_banner_is_informational_when_fresh(client: TestClient, repo: Repository):
    """A freshly-uploaded CSV produces an informational (non-stale) banner."""
    fresh_as_of = (date.today() - timedelta(days=3)).isoformat()
    repo.save_broker_positions(
        rows=[
            {
                "account_label": "Schwab/Taxable",
                "symbol": "AAPL",
                "qty": 10,
                "cost_basis": 1000,
                "market_value": 1500,
                "unrealized_pl": 500,
            }
        ],
        as_of_date=fresh_as_of,
    )
    html = client.get("/verify").text
    assert 'data-freshness-severity="ok"' in html
    assert "3 days old" in html
