from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

from net_alpha.db.migrations import migrate
from net_alpha.db.repository import Repository
from net_alpha.targets.models import TargetUnit


@pytest.fixture
def repo() -> Repository:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        migrate(s)
    return Repository(engine)


def test_upsert_creates_then_updates(repo: Repository):
    # Create.
    t1 = repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    assert t1.symbol == "HIMS"
    assert t1.target_amount == Decimal("1000")
    assert t1.target_unit == TargetUnit.USD
    first_created = t1.created_at

    # Update — same symbol, different amount.
    t2 = repo.upsert_target("HIMS", Decimal("2000"), TargetUnit.SHARES)
    assert t2.target_amount == Decimal("2000")
    assert t2.target_unit == TargetUnit.SHARES
    assert t2.created_at == first_created  # preserved
    assert t2.updated_at >= first_created  # bumped


def test_get_target_returns_none_for_unknown(repo: Repository):
    assert repo.get_target("NOPE") is None


def test_list_targets_returns_alphabetical(repo: Repository):
    repo.upsert_target("VOO", Decimal("10000"), TargetUnit.USD)
    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    repo.upsert_target("MSFT", Decimal("5000"), TargetUnit.USD)
    syms = [t.symbol for t in repo.list_targets()]
    assert syms == ["HIMS", "MSFT", "VOO"]


def test_delete_target(repo: Repository):
    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    assert repo.delete_target("HIMS") is True
    assert repo.delete_target("HIMS") is False  # already gone
    assert repo.get_target("HIMS") is None


def test_symbol_uppercased(repo: Repository):
    t = repo.upsert_target("hims", Decimal("1000"), TargetUnit.USD)
    assert t.symbol == "HIMS"
    assert repo.get_target("HIMS").target_amount == Decimal("1000")
    assert repo.get_target("hims").target_amount == Decimal("1000")  # case-insensitive lookup


def test_list_targets_includes_tags(repo: Repository):
    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    repo.upsert_target("VOO", Decimal("10000"), TargetUnit.USD)
    repo.set_target_tags("HIMS", ["core", "income"])
    repo.set_target_tags("VOO", ["etf"])
    by_sym = {t.symbol: t for t in repo.list_targets()}
    assert by_sym["HIMS"].tags == ("core", "income")
    assert by_sym["VOO"].tags == ("etf",)


def test_list_targets_empty_tags_when_none_set(repo: Repository):
    repo.upsert_target("AAPL", Decimal("500"), TargetUnit.USD)
    by_sym = {t.symbol: t for t in repo.list_targets()}
    assert by_sym["AAPL"].tags == ()


def test_get_target_includes_tags(repo: Repository):
    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    repo.set_target_tags("HIMS", ["core"])
    t = repo.get_target("HIMS")
    assert t is not None
    assert t.tags == ("core",)


def test_list_targets_includes_sort_order(repo: Repository):
    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    targets = repo.list_targets()
    assert len(targets) == 1
    # First insert into a fresh DB lands at sort_order = 1.
    assert targets[0].sort_order == 1


def test_upsert_assigns_max_sort_order_plus_one_on_insert(repo: Repository):
    a = repo.upsert_target("AAPL", Decimal("1"), TargetUnit.USD)
    b = repo.upsert_target("BBB",  Decimal("1"), TargetUnit.USD)
    c = repo.upsert_target("CCC",  Decimal("1"), TargetUnit.USD)
    assert (a.sort_order, b.sort_order, c.sort_order) == (1, 2, 3)


def test_upsert_preserves_sort_order_on_update(repo: Repository):
    repo.upsert_target("AAPL", Decimal("1"), TargetUnit.USD)
    b1 = repo.upsert_target("BBB", Decimal("1"), TargetUnit.USD)
    assert b1.sort_order == 2

    # Update BBB — sort_order must not change.
    b2 = repo.upsert_target("BBB", Decimal("999"), TargetUnit.SHARES)
    assert b2.sort_order == 2


def test_list_targets_by_manual_order_orders_by_sort_order(repo: Repository):
    repo.upsert_target("AAA", Decimal("1"), TargetUnit.USD)  # sort_order 1
    repo.upsert_target("BBB", Decimal("1"), TargetUnit.USD)  # sort_order 2
    repo.upsert_target("CCC", Decimal("1"), TargetUnit.USD)  # sort_order 3
    syms = [t.symbol for t in repo.list_targets_by_manual_order()]
    assert syms == ["AAA", "BBB", "CCC"]


def test_list_targets_by_manual_order_breaks_ties_by_symbol(repo: Repository):
    """If two rows share a sort_order, fall back to symbol asc for stability."""
    from sqlalchemy import text as _text
    from sqlmodel import Session as _Session
    repo.upsert_target("ZZZ", Decimal("1"), TargetUnit.USD)
    repo.upsert_target("AAA", Decimal("1"), TargetUnit.USD)
    # Force both to sort_order = 5.
    with _Session(repo.engine) as s:
        s.exec(_text("UPDATE position_targets SET sort_order = 5"))
        s.commit()
    syms = [t.symbol for t in repo.list_targets_by_manual_order()]
    assert syms == ["AAA", "ZZZ"]


def test_list_targets_by_manual_order_includes_tags(repo: Repository):
    repo.upsert_target("HIMS", Decimal("1000"), TargetUnit.USD)
    repo.set_target_tags("HIMS", ["core"])
    rows = repo.list_targets_by_manual_order()
    assert rows[0].tags == ("core",)
