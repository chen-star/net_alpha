"""Real production-path test: import → recompute_all_violations → exempt matches + classifications persisted.

Exercises the full import pipeline WITHOUT setting is_section_1256 explicitly on the
Trade objects — relying on auto-detection in add_import (C1 fix). Then verifies that
recompute_all_violations (the production recompute path) persists exempt matches and
§1256 classifications (C2 fix).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlmodel import Session, SQLModel, create_engine

import net_alpha.db.tables  # noqa: F401 — register table metadata
from net_alpha.db.migrations import migrate
from net_alpha.db.repository import Repository
from net_alpha.engine.etf_pairs import load_etf_pairs
from net_alpha.engine.recompute import recompute_all_violations
from net_alpha.models.domain import ImportRecord, OptionDetails, Trade


@pytest.fixture()
def repo(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        migrate(session)
    return Repository(engine)


def test_production_path_persists_exempt_matches_and_classifications(repo):
    """Import SPX option trades via add_import WITHOUT setting is_section_1256 explicitly.

    Verifies:
    1. (C1) add_import auto-detects §1256 status — all SPX option rows have is_section_1256=True.
    2. (C2) recompute_all_violations persists exempt matches (SPX pair not treated as wash sale).
    3. (C2) recompute_all_violations runs the §1256 classifier and persists classifications.
    4. No wash-sale violations are produced for §1256 pairs.
    """
    acct = repo.get_or_create_account("schwab", "personal")
    spx_opt = OptionDetails(strike=4500, expiry=date(2025, 12, 19), call_put="C")

    # NOTE: is_section_1256 is NOT set on these trades — relying on auto-detection in add_import.
    spx_loss = Trade(
        date=date(2024, 9, 15),
        account="schwab/personal",
        ticker="SPX",
        action="Sell",
        quantity=1,
        proceeds=100.0,
        cost_basis=721.50,
        option_details=spx_opt,
    )
    spx_rebuy = Trade(
        date=date(2024, 9, 22),
        account="schwab/personal",
        ticker="SPX",
        action="Buy",
        quantity=1,
        proceeds=None,
        cost_basis=150.0,
        option_details=spx_opt,
    )

    rec = ImportRecord(
        account_id=acct.id,
        csv_filename="test_spx.csv",
        csv_sha256="test_sha",
        imported_at=datetime(2024, 10, 1),
        trade_count=2,
    )
    repo.add_import(acct, rec, [spx_loss, spx_rebuy])

    # C1: Verify is_section_1256 was auto-detected during import.
    loaded = repo.all_trades()
    spx_trades = [t for t in loaded if t.ticker == "SPX"]
    assert len(spx_trades) == 2, f"Expected 2 SPX trades, got {len(spx_trades)}"
    for t in spx_trades:
        assert t.is_section_1256, (
            f"Trade {t.id} (SPX {t.action} {t.date}) should have is_section_1256=True "
            "after add_import auto-detection (C1 fix)"
        )

    # Run the production recompute path (NOT recompute_all — the production callers use this).
    recompute_all_violations(repo, etf_pairs=load_etf_pairs())

    # C2: Production path must have persisted exempt matches.
    exempts = repo.list_exempt_matches()
    assert len(exempts) == 1, f"Expected 1 exempt match for SPX §1256 pair, got {len(exempts)}"
    assert exempts[0].ticker == "SPX"
    assert exempts[0].exempt_reason == "section_1256"

    # C2: No regular wash-sale violations for §1256 pairs.
    violations = repo.all_violations()
    assert violations == [], f"Expected no wash-sale violations for SPX §1256 trades, got {violations}"

    # C2: Production path must have run the §1256 classifier.
    classifications = repo.list_section_1256_classifications()
    # Only the Sell (loss) trade produces a classification; the Buy does not.
    assert len(classifications) == 1, f"Expected 1 §1256 classification (for the Sell), got {len(classifications)}"
    c = classifications[0]
    assert c.underlying == "SPX"
    # The classifier computes proceeds - FIFO lot basis.
    # The Buy creates a Lot with adjusted_basis=150. The Sell has proceeds=100.
    # realized_pnl = 100 - 150 = -50.
    expected_pnl = Decimal("100") - Decimal("150")
    assert abs(c.realized_pnl - expected_pnl) < Decimal("0.01"), (
        f"Expected realized_pnl ≈ {expected_pnl} (proceeds - lot_basis), got {c.realized_pnl}"
    )


def test_add_import_preserves_explicit_flag(repo):
    """If the caller DOES set is_section_1256=True, add_import must preserve it (not clobber)."""
    acct = repo.get_or_create_account("schwab", "test")
    # Equity trade (no option_details) manually tagged as §1256 — unusual but
    # must be respected (e.g. cash-settled futures that look like equities).
    explicit_trade = Trade(
        date=date(2024, 6, 1),
        account="schwab/test",
        ticker="SPX",
        action="Sell",
        quantity=1,
        proceeds=500.0,
        cost_basis=400.0,
        is_section_1256=True,  # explicitly set
    )
    rec = ImportRecord(
        account_id=acct.id,
        csv_filename="explicit.csv",
        csv_sha256="sha_explicit",
        imported_at=datetime(2024, 7, 1),
        trade_count=1,
    )
    repo.add_import(acct, rec, [explicit_trade])
    loaded = repo.all_trades()
    assert loaded[0].is_section_1256 is True, "Explicit is_section_1256=True must be preserved"


def test_recompute_all_violations_stamps_meta(repo):
    """After recompute_all_violations, universe hash and engine version meta rows are stamped."""
    from sqlalchemy import text
    from sqlmodel import Session

    from net_alpha.db.migrations import CURRENT_SCHEMA_VERSION
    from net_alpha.section_1256.universe import universe_hash

    acct = repo.get_or_create_account("schwab", "meta_test")
    # A trivial TSLA trade so there is data and the recompute actually runs.
    t = Trade(
        date=date(2024, 5, 1),
        account="schwab/meta_test",
        ticker="TSLA",
        action="Sell",
        quantity=1,
        proceeds=200.0,
        cost_basis=300.0,
    )
    rec = ImportRecord(
        account_id=acct.id,
        csv_filename="meta.csv",
        csv_sha256="sha_meta",
        imported_at=datetime(2024, 6, 1),
        trade_count=1,
    )
    repo.add_import(acct, rec, [t])
    recompute_all_violations(repo, etf_pairs=load_etf_pairs())

    with Session(repo.engine) as session:
        hash_row = session.exec(text("SELECT value FROM meta WHERE key='section_1256_universe_hash'")).first()
        version_row = session.exec(text("SELECT value FROM meta WHERE key='wash_sale_engine_version'")).first()

    assert hash_row is not None, "section_1256_universe_hash meta row must be stamped"
    assert hash_row[0] == universe_hash(), "Stamped universe hash must match current hash"
    assert version_row is not None, "wash_sale_engine_version meta row must be stamped"
    assert version_row[0] == str(CURRENT_SCHEMA_VERSION), (
        f"Stamped engine version must match CURRENT_SCHEMA_VERSION={CURRENT_SCHEMA_VERSION}"
    )
