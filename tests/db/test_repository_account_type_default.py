"""Audit #13: missing/unknown account-type rows must default to TAXABLE
consistently across helpers.

Two divergent defaults existed:
  - account_types_by_display() — wash-sale detector input — defaulted unknown
    string types to TAXABLE (try/except on AccountType()).
  - _taxable_account_ids() / _taxable_account_displays() — tax helpers —
    whitelisted only the literal string "taxable", so any unknown type
    ("weird", "TAXABLE", "trad-ira" with a stray hyphen, etc.) was silently
    treated as NON-taxable.

The schema enforces NOT NULL DEFAULT 'taxable' on accounts.type, so a true
NULL value is not reachable through normal code paths, but a future migration
step or manual edit could introduce an unrecognized string. Either side could
change which P&L gets taxed without the user knowing. The fix reconciles both
to TAXABLE for unknown strings, and emits a one-shot warning (per recompute)
so the user can correct the row.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlmodel import Session, create_engine

import net_alpha.db.tables  # noqa: F401 — register SQLModel metadata
from net_alpha.db.connection import init_db
from net_alpha.db.repository import Repository
from net_alpha.models.accounts import AccountType


@pytest.fixture()
def repo():
    engine = create_engine("sqlite://")
    init_db(engine)
    return Repository(engine)


def _force_account_type(repo: Repository, *, broker: str, label: str, type_value: str) -> None:
    """Bypass the validating set_account_type() to write an unknown-string type
    into the underlying row (simulates legacy migration / manual-edit data)."""
    with Session(repo.engine) as s:
        s.exec(
            text("UPDATE accounts SET type=:t WHERE broker=:b AND label=:l").bindparams(
                t=type_value, b=broker, l=label
            )
        )
        s.commit()


def test_account_types_by_display_defaults_unknown_to_taxable(repo):
    repo.get_or_create_account("Schwab", "Weird")
    _force_account_type(repo, broker="Schwab", label="Weird", type_value="weird")

    out = repo.account_types_by_display()
    assert out["Schwab/Weird"] == AccountType.TAXABLE


def test_taxable_account_ids_treats_unknown_as_taxable(repo):
    repo.get_or_create_account("Schwab", "Weird")
    repo.get_or_create_account("Schwab", "Roth")
    repo.set_account_type(broker="Schwab", label="Roth", type_="roth_ira")
    _force_account_type(repo, broker="Schwab", label="Weird", type_value="weird")

    with Session(repo.engine) as s:
        taxable_ids = set(repo._taxable_account_ids(s))
        weird = s.exec(text("SELECT id FROM accounts WHERE label='Weird'")).first()[0]
        roth = s.exec(text("SELECT id FROM accounts WHERE label='Roth'")).first()[0]

    assert weird in taxable_ids, "unknown-string type should default to TAXABLE"
    assert roth not in taxable_ids


def test_taxable_account_displays_treats_unknown_as_taxable(repo):
    repo.get_or_create_account("Schwab", "Weird")
    repo.get_or_create_account("Schwab", "Roth")
    repo.set_account_type(broker="Schwab", label="Roth", type_="roth_ira")
    _force_account_type(repo, broker="Schwab", label="Weird", type_value="weird")

    with Session(repo.engine) as s:
        taxable_displays = repo._taxable_account_displays(s)

    assert "Schwab/Weird" in taxable_displays
    assert "Schwab/Roth" not in taxable_displays


def test_recompute_emits_one_warning_per_unmapped_account(repo, caplog):
    """Audit #13: recompute_all_violations should log a single warning naming
    every unmapped/unknown account-type row so the user knows to classify them.
    The warning is per-recompute, not per-trade."""
    from datetime import date, datetime

    from net_alpha.engine.recompute import recompute_all_violations
    from net_alpha.models.domain import ImportRecord, Trade

    # Two unmapped (unknown-string-typed) accounts + one explicit type. Seed
    # one trade in each so the detector window is non-empty.
    a1 = repo.get_or_create_account("Schwab", "MysteryA")
    a2 = repo.get_or_create_account("Schwab", "MysteryB")
    a3 = repo.get_or_create_account("Schwab", "Roth")
    repo.set_account_type(broker="Schwab", label="Roth", type_="roth_ira")
    _force_account_type(repo, broker="Schwab", label="MysteryA", type_value="frobnitz")
    _force_account_type(repo, broker="Schwab", label="MysteryB", type_value="qux")

    for acct, display in (
        (a1, "Schwab/MysteryA"),
        (a2, "Schwab/MysteryB"),
        (a3, "Schwab/Roth"),
    ):
        record = ImportRecord(
            account_id=acct.id,
            csv_filename=f"seed-{display}.csv",
            csv_sha256=f"sha-{display}",
            imported_at=datetime.now(),
            trade_count=1,
        )
        repo.add_import(
            acct,
            record,
            [
                Trade(
                    account=display,
                    date=date(2025, 1, 5),
                    ticker="AAPL",
                    action="Buy",
                    quantity=1.0,
                    proceeds=None,
                    cost_basis=100.0,
                )
            ],
        )

    # Capture loguru via its native handler interception — loguru does NOT
    # propagate to logging by default, so caplog won't see it without a sink.
    from loguru import logger

    seen: list[str] = []
    sink_id = logger.add(lambda m: seen.append(m), level="WARNING")
    try:
        recompute_all_violations(repo, etf_pairs={})
    finally:
        logger.remove(sink_id)

    unmapped_warnings = [m for m in seen if "unmapped" in m.lower() or "unknown account" in m.lower()]
    assert len(unmapped_warnings) == 1, (
        f"expected exactly one unmapped-account warning per recompute, "
        f"got {len(unmapped_warnings)}: {unmapped_warnings}"
    )
    # Both unmapped account display strings should appear in the warning.
    msg = unmapped_warnings[0]
    assert "Schwab/MysteryA" in msg
    assert "Schwab/MysteryB" in msg
    # The classified account should NOT be in the warning.
    assert "Schwab/Roth" not in msg
