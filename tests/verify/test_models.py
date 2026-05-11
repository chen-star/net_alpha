from datetime import datetime

from net_alpha.verify.models import VerifyFinding, VerifyResult


def test_verify_result_defaults():
    vr = VerifyResult(
        run_at=datetime(2026, 5, 11, 4, 30).isoformat(),
        trigger="scheduled",
        status="ok",
        duration_ms=42,
        checks_total=10,
        checks_passed=10,
        checks_warned=0,
        checks_failed=0,
    )
    assert vr.reference_age_days is None
    assert vr.notes is None
    assert vr.id is None  # not yet inserted


def test_verify_finding_defaults():
    vf = VerifyFinding(
        run_id=1,
        rule_id="OV-1",
        severity="fail",
        scope="global",
    )
    assert vf.ours is None
    assert vf.theirs is None
    assert vf.delta is None
    assert vf.detail_json is None
