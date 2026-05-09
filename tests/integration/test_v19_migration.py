"""End-to-end: existing accounts row → migrate → type defaults to 'taxable' and is editable."""

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

import net_alpha.db.tables as _tables  # noqa: F401
from net_alpha.db.migrations import migrate


def test_migration_preserves_existing_accounts_with_taxable_default():
    """Existing account rows inserted before migration get type='taxable'.

    Simulates upgrading from v18 to v19: creates a v18-schema DB with legacy
    account rows (no type/created_at columns), then runs migrate and verifies
    the columns are added and backfilled.
    """
    engine = create_engine("sqlite:///:memory:")

    # Create a minimal v18 schema by creating the meta and accounts tables
    # without the v19 columns.
    with Session(engine) as s:
        s.exec(text("""
            CREATE TABLE meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """))
        s.exec(text("""
            CREATE TABLE accounts (
                id INTEGER PRIMARY KEY,
                broker TEXT NOT NULL,
                label TEXT NOT NULL,
                UNIQUE(broker, label)
            )
        """))
        # Stamp this as v18
        s.exec(text("INSERT INTO meta(key, value) VALUES ('schema_version', '18')"))

        # Insert legacy account rows BEFORE the migration's column-add runs.
        s.exec(text("INSERT INTO accounts(broker, label) VALUES('schwab', 'personal')"))
        s.exec(text("INSERT INTO accounts(broker, label) VALUES('schwab', 'roth')"))
        s.commit()

    # Now run the migration which should add type and created_at columns
    with Session(engine) as s:
        migrate(s)

        # Verify both rows now have type='taxable' and created_at is filled
        rows = list(s.exec(text(
            "SELECT broker, label, type FROM accounts ORDER BY broker, label"
        )).all())
        labels = [(r[0], r[1], r[2]) for r in rows]
        # Both rows present with type defaulted to 'taxable'
        assert ("schwab", "personal", "taxable") in labels
        assert ("schwab", "roth", "taxable") in labels

        # Verify created_at was backfilled (non-NULL)
        created_rows = list(s.exec(text(
            "SELECT broker, label, created_at FROM accounts ORDER BY broker, label"
        )).all())
        for row in created_rows:
            assert row[2] is not None, f"created_at should be backfilled for {row[0]}/{row[1]}"


def test_migration_v19_idempotent():
    """Running migrate twice should be a no-op for v19 column adds."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        migrate(s)
        migrate(s)  # second call must not raise
