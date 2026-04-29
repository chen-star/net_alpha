"""Recompute should:
1. Persist exempt matches via repository
2. Run the §1256 classifier and persist classifications
3. Trigger a full recompute when the universe hash changes
"""

from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

import net_alpha.db.tables  # noqa: F401 — register metadata
from net_alpha.db.migrations import migrate
from net_alpha.db.repository import Repository
from net_alpha.engine.recompute import recompute_all, should_full_recompute
from net_alpha.models.domain import ImportRecord, OptionDetails, Trade


@pytest.fixture()
def repo(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        migrate(session)
    return Repository(engine)


def _seed_import(repo: Repository, trades: list[Trade]) -> None:
    """Create account 'test/personal' and add trades via add_import."""
    account = repo.get_or_create_account(broker="test", label="personal")
    record = ImportRecord(
        account_id=account.id,
        csv_filename="test.csv",
        csv_sha256="sha-test",
        imported_at=datetime.now(),
        trade_count=len(trades),
    )
    repo.add_import(account, record, trades)


def _spx_loss() -> Trade:
    return Trade(
        date=date(2024, 9, 15),
        account="test/personal",
        ticker="SPX",
        action="Sell",
        quantity=1,
        proceeds=Decimal("100"),
        cost_basis=Decimal("721.50"),
        option_details=OptionDetails(strike=4500, expiry=date(2025, 12, 19), call_put="C"),
        is_section_1256=True,
    )


def _spx_buy() -> Trade:
    return Trade(
        date=date(2024, 9, 22),
        account="test/personal",
        ticker="SPX",
        action="Buy",
        quantity=1,
        proceeds=Decimal("100"),
        cost_basis=Decimal("100"),
        option_details=OptionDetails(strike=4500, expiry=date(2025, 12, 19), call_put="C"),
        is_section_1256=True,
    )


def test_recompute_persists_exempt_matches(repo):
    _seed_import(repo, [_spx_loss(), _spx_buy()])
    recompute_all(repo)
    assert len(repo.list_exempt_matches()) == 1


def test_recompute_persists_section_1256_classifications(repo):
    _seed_import(repo, [_spx_loss(), _spx_buy()])
    recompute_all(repo)
    classifications = repo.list_section_1256_classifications()
    # Only the sell is "closed" (the buy has no offsetting sell)
    assert len(classifications) == 1


def test_should_full_recompute_returns_true_when_universe_hash_changes(repo):
    # Stamp a stale hash in meta
    with Session(repo.engine) as session:
        session.exec(text("UPDATE meta SET value='deadbeef' WHERE key='section_1256_universe_hash'"))
        session.commit()
    assert should_full_recompute(repo) is True


def test_should_full_recompute_returns_false_when_universe_hash_matches(repo):
    # Migration stamped current hash; nothing changed since
    assert should_full_recompute(repo) is False
