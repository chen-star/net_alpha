from __future__ import annotations

from datetime import date, datetime

import pytest

from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.models.domain import Account, ImportRecord, Trade
from net_alpha.models.realized_gl import RealizedGLLot


@pytest.fixture
def repo(tmp_path):
    engine = get_engine(tmp_path / "t.db")
    init_db(engine)
    return Repository(engine)


def _make_lot(**overrides) -> RealizedGLLot:
    base = dict(
        account_display="schwab/personal",
        symbol_raw="WRD",
        ticker="WRD",
        closed_date=date(2026, 4, 20),
        opened_date=date(2026, 2, 11),
        quantity=100.0,
        proceeds=824.96,
        cost_basis=800.66,
        unadjusted_cost_basis=800.66,
        wash_sale=False,
        disallowed_loss=0.0,
        term="Short Term",
    )
    base.update(overrides)
    return RealizedGLLot(**base)


def _make_account(repo: Repository) -> Account:
    return repo.get_or_create_account("schwab", "personal")


def _make_import(repo: Repository, acct: Account) -> int:
    rec = ImportRecord(
        account_id=acct.id,
        csv_filename="t.csv",
        csv_sha256="abc",
        imported_at=datetime(2026, 4, 25, 0, 0, 0),
        trade_count=0,
    )
    result = repo.add_import(acct, rec, [])
    return result.import_id


def test_add_gl_lots_inserts_rows(repo):
    acct = _make_account(repo)
    import_id = _make_import(repo, acct)
    lots = [_make_lot()]
    inserted = repo.add_gl_lots(acct, import_id, lots)
    assert inserted == 1


def test_add_gl_lots_dedupes_on_natural_key(repo):
    acct = _make_account(repo)
    import_id = _make_import(repo, acct)
    lot = _make_lot()
    repo.add_gl_lots(acct, import_id, [lot])
    second = repo.add_gl_lots(acct, import_id, [lot])  # same lot, second time
    assert second == 0


def test_get_gl_lots_for_match_returns_matching_rows(repo):
    acct = _make_account(repo)
    import_id = _make_import(repo, acct)
    lot = _make_lot()
    repo.add_gl_lots(acct, import_id, [lot])
    result = repo.get_gl_lots_for_match(account_id=acct.id, symbol_raw="WRD", closed_date=date(2026, 4, 20))
    assert len(result) == 1
    assert result[0].cost_basis == 800.66


def test_get_gl_lots_for_match_returns_empty_when_no_match(repo):
    acct = _make_account(repo)
    import_id = _make_import(repo, acct)
    repo.add_gl_lots(acct, import_id, [_make_lot()])
    result = repo.get_gl_lots_for_match(account_id=acct.id, symbol_raw="AAPL", closed_date=date(2026, 4, 20))
    assert result == []


def test_get_sells_needing_basis_returns_only_sells(repo):
    acct = _make_account(repo)
    rec = ImportRecord(
        account_id=acct.id,
        csv_filename="t.csv",
        csv_sha256="abc",
        imported_at=datetime(2026, 4, 25),
        trade_count=2,
    )
    trades = [
        Trade(
            account=acct.display(),
            date=date(2026, 4, 1),
            ticker="AAPL",
            action="Buy",
            quantity=1,
            cost_basis=100.0,
        ),
        Trade(
            account=acct.display(),
            date=date(2026, 4, 20),
            ticker="AAPL",
            action="Sell",
            quantity=1,
            proceeds=90.0,
        ),
    ]
    repo.add_import(acct, rec, trades)
    sells = repo.get_sells_for_account(acct.id)
    assert len(sells) == 1
    assert sells[0].ticker == "AAPL"
    assert sells[0].action == "Sell"


def test_update_trade_basis_writes_basis_and_source(repo):
    acct = _make_account(repo)
    rec = ImportRecord(
        account_id=acct.id,
        csv_filename="t.csv",
        csv_sha256="abc",
        imported_at=datetime(2026, 4, 25),
        trade_count=1,
    )
    trades = [
        Trade(
            account=acct.display(),
            date=date(2026, 4, 20),
            ticker="AAPL",
            action="Sell",
            quantity=1,
            proceeds=90.0,
        ),
    ]
    repo.add_import(acct, rec, trades)
    sells = repo.get_sells_for_account(acct.id)
    sell_id = sells[0].id
    repo.update_trade_basis(sell_id, cost_basis=120.0, basis_source="g_l")
    sells_after = repo.get_sells_for_account(acct.id)
    assert sells_after[0].cost_basis == 120.0
    assert sells_after[0].basis_source == "g_l"


def test_get_buys_before_date_returns_buy_trades_oldest_first(repo):
    acct = _make_account(repo)
    rec = ImportRecord(
        account_id=acct.id,
        csv_filename="t.csv",
        csv_sha256="abc",
        imported_at=datetime(2026, 4, 25),
        trade_count=2,
    )
    trades = [
        Trade(
            account=acct.display(),
            date=date(2026, 3, 15),
            ticker="AAPL",
            action="Buy",
            quantity=10,
            cost_basis=1000.0,
        ),
        Trade(
            account=acct.display(),
            date=date(2026, 3, 10),
            ticker="AAPL",
            action="Buy",
            quantity=5,
            cost_basis=500.0,
        ),
        Trade(
            account=acct.display(),
            date=date(2026, 4, 1),
            ticker="AAPL",
            action="Buy",
            quantity=3,
            cost_basis=300.0,
        ),
    ]
    repo.add_import(acct, rec, trades)
    buys = repo.get_buys_before_date(account_id=acct.id, ticker="AAPL", before_date=date(2026, 3, 31))
    assert [b.date for b in buys] == [date(2026, 3, 10), date(2026, 3, 15)]


def test_get_gl_lots_for_ticker_returns_all_lots(repo):
    acct = _make_account(repo)
    import_id = _make_import(repo, acct)
    repo.add_gl_lots(
        acct,
        import_id,
        [
            _make_lot(opened_date=date(2026, 2, 11)),
            _make_lot(opened_date=date(2026, 3, 1)),
        ],
    )
    lots = repo.get_gl_lots_for_ticker(acct.id, "WRD")
    assert len(lots) == 2


def test_remove_import_cascade_deletes_gl_lots(repo):
    """Removing an import must delete its G/L lot rows to prevent orphans."""
    acct = _make_account(repo)
    rec = ImportRecord(
        account_id=acct.id,
        csv_filename="t.csv",
        csv_sha256="abc",
        imported_at=datetime(2026, 4, 25),
        trade_count=0,
    )
    result = repo.add_import(acct, rec, [])
    repo.add_gl_lots(acct, result.import_id, [_make_lot()])
    assert len(repo.get_gl_lots_for_ticker(acct.id, "WRD")) == 1
    repo.remove_import(result.import_id)
    # G/L lots tied to that import must be gone
    assert len(repo.get_gl_lots_for_ticker(acct.id, "WRD")) == 0
