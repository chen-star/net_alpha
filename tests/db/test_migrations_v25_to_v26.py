"""v25 → v26: accounts.broker_label column for positions-CSV → account alias mapping.

A Schwab per-account positions CSV writes a header like
"Positions for account Short Term ...180 as of ..."; the user's trades
import under a different account label (e.g., "st"). v26 adds an opt-in
alias column so the verify reconciler can join the two.
"""

from sqlalchemy import text

from net_alpha.db.migrations import (
    CURRENT_SCHEMA_VERSION,
    _column_exists,
    _migrate_v25_to_v26,
)


def test_current_schema_version_is_26():
    assert CURRENT_SCHEMA_VERSION == 26


def test_v25_to_v26_adds_broker_label_column(in_memory_session_at_v25):
    session = in_memory_session_at_v25
    assert not _column_exists(session, "accounts", "broker_label")
    _migrate_v25_to_v26(session)
    assert _column_exists(session, "accounts", "broker_label")


def test_v25_to_v26_preserves_existing_account_rows(in_memory_session_at_v25):
    session = in_memory_session_at_v25
    session.exec(
        text("INSERT INTO accounts(broker, label, type, created_at) VALUES ('schwab', 'st', 'taxable', '2026-05-01')")
    )
    session.commit()
    _migrate_v25_to_v26(session)
    rows = list(session.exec(text("SELECT label, broker_label FROM accounts WHERE label='st'")).all())
    assert len(rows) == 1
    # Existing rows get NULL broker_label until the user maps one.
    assert rows[0][0] == "st"
    assert rows[0][1] is None


def test_v25_to_v26_is_idempotent(in_memory_session_at_v25):
    session = in_memory_session_at_v25
    _migrate_v25_to_v26(session)
    _migrate_v25_to_v26(session)  # second call must not error
    assert _column_exists(session, "accounts", "broker_label")
