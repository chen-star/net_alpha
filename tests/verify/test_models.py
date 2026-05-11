from datetime import datetime

from net_alpha.verify.models import BrokerPosition, VerifyFinding, VerifyResult


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


def test_broker_position_required_fields():
    bp = BrokerPosition(
        import_id=1,
        account_label="Schwab-Taxable",
        symbol="AAPL",
        qty=100.0,
        cost_basis=15000.0,
        market_value=17500.0,
        unrealized_pl=2500.0,
        as_of_date="2026-05-10",
    )
    assert bp.id is None
    assert bp.symbol == "AAPL"
    assert bp.qty == 100.0
