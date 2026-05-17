"""v23 → v24: verify_result, verify_finding, broker_position tables for the verification engine."""

from sqlalchemy import text

from net_alpha.db.migrations import (
    CURRENT_SCHEMA_VERSION,
    _migrate_v23_to_v24,
    _table_exists,
)


def test_v24_constant_is_26():
    assert CURRENT_SCHEMA_VERSION == 26


def test_v23_to_v24_creates_verify_result_table(in_memory_session_at_v23):
    session = in_memory_session_at_v23
    assert not _table_exists(session, "verify_result")
    _migrate_v23_to_v24(session)
    assert _table_exists(session, "verify_result")
    cols = [r[1] for r in session.exec(text("PRAGMA table_info(verify_result)")).all()]
    for required in [
        "id",
        "run_at",
        "trigger",
        "status",
        "duration_ms",
        "checks_total",
        "checks_passed",
        "checks_warned",
        "checks_failed",
        "reference_age_days",
        "notes",
    ]:
        assert required in cols, f"missing column {required}"


def test_v23_to_v24_creates_verify_finding_table(in_memory_session_at_v23):
    session = in_memory_session_at_v23
    _migrate_v23_to_v24(session)
    assert _table_exists(session, "verify_finding")
    cols = [r[1] for r in session.exec(text("PRAGMA table_info(verify_finding)")).all()]
    for required in [
        "id",
        "run_id",
        "rule_id",
        "severity",
        "scope",
        "ours",
        "theirs",
        "delta",
        "detail_json",
    ]:
        assert required in cols


def test_v23_to_v24_creates_broker_position_table(in_memory_session_at_v23):
    session = in_memory_session_at_v23
    _migrate_v23_to_v24(session)
    assert _table_exists(session, "broker_position")
    cols = [r[1] for r in session.exec(text("PRAGMA table_info(broker_position)")).all()]
    for required in [
        "id",
        "import_id",
        "account_label",
        "symbol",
        "qty",
        "cost_basis",
        "market_value",
        "unrealized_pl",
        "as_of_date",
    ]:
        assert required in cols


def test_v23_to_v24_is_idempotent(in_memory_session_at_v23):
    session = in_memory_session_at_v23
    _migrate_v23_to_v24(session)
    _migrate_v23_to_v24(session)  # second call must not error
    assert _table_exists(session, "verify_result")
