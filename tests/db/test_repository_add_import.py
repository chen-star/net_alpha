from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlmodel import SQLModel, create_engine

from net_alpha.db.repository import Repository
from net_alpha.models.domain import ImportRecord, OptionDetails, Trade


@pytest.fixture
def repo(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/v2.db")
    SQLModel.metadata.create_all(eng)
    return Repository(eng)


def _trade(account: str, ticker: str, qty: float, basis: float = 1000.0):
    return Trade(account=account, date=date(2024, 1, 1), ticker=ticker, action="Buy", quantity=qty, cost_basis=basis)


def test_add_import_inserts_account_record_and_trades(repo):
    acct = repo.get_or_create_account("schwab", "personal")
    rec = ImportRecord(
        account_id=acct.id, csv_filename="q1.csv", csv_sha256="h", imported_at=datetime(2026, 4, 25), trade_count=0
    )
    trades = [_trade(acct.display(), "TSLA", 10), _trade(acct.display(), "AAPL", 5)]
    result = repo.add_import(acct, rec, trades)
    assert result.new_trades == 2
    assert result.duplicate_trades == 0
    assert result.import_id is not None


def test_existing_natural_keys_returns_set(repo):
    acct = repo.get_or_create_account("schwab", "personal")
    assert repo.existing_natural_keys(acct.id) == set()


def test_re_adding_same_trades_under_same_account_skips_dups(repo):
    acct = repo.get_or_create_account("schwab", "personal")
    rec1 = ImportRecord(
        account_id=acct.id, csv_filename="q1.csv", csv_sha256="h1", imported_at=datetime(2026, 4, 25), trade_count=0
    )
    rec2 = ImportRecord(
        account_id=acct.id,
        csv_filename="q1_again.csv",
        csv_sha256="h2",
        imported_at=datetime(2026, 4, 26),
        trade_count=0,
    )
    trades = [_trade(acct.display(), "TSLA", 10), _trade(acct.display(), "AAPL", 5)]

    repo.add_import(acct, rec1, trades)

    # Caller is responsible for filtering with existing_natural_keys before add_import.
    keys = repo.existing_natural_keys(acct.id)
    new_trades = [t for t in trades if t.compute_natural_key() not in keys]
    result = repo.add_import(acct, rec2, new_trades)
    assert result.new_trades == 0
    assert result.duplicate_trades == 0  # caller already filtered them


def test_same_natural_key_in_different_account_is_independent(repo):
    a = repo.get_or_create_account("schwab", "personal")
    b = repo.get_or_create_account("schwab", "roth")
    rec_a = ImportRecord(
        account_id=a.id, csv_filename="a.csv", csv_sha256="h", imported_at=datetime(2026, 4, 25), trade_count=0
    )
    rec_b = ImportRecord(
        account_id=b.id, csv_filename="b.csv", csv_sha256="h", imported_at=datetime(2026, 4, 25), trade_count=0
    )
    repo.add_import(a, rec_a, [_trade(a.display(), "TSLA", 10)])
    result = repo.add_import(b, rec_b, [_trade(b.display(), "TSLA", 10)])
    assert result.new_trades == 1


def test_within_batch_duplicates_do_not_silently_drop_neighbors(repo):
    """Two trades sharing a natural key inside a single add_import batch must
    NOT cascade into losing all preceding flushed trades. The pre-fix code
    caught IntegrityError with `s.rollback()`, which unwinds the entire
    SQLAlchemy session — so even one within-batch duplicate could silently
    delete hundreds of valid trades imported moments earlier in the same call.
    """
    acct = repo.get_or_create_account("schwab", "personal")
    rec = ImportRecord(
        account_id=acct.id, csv_filename="q.csv", csv_sha256="h", imported_at=datetime(2026, 4, 25), trade_count=0
    )
    a = _trade(acct.display(), "TSLA", 10)
    # Same canonical fields → same natural key → would trigger IntegrityError
    # in the old loop and rollback every trade flushed before it.
    a_dup = _trade(acct.display(), "TSLA", 10)
    b = _trade(acct.display(), "AAPL", 5)
    c = _trade(acct.display(), "MSFT", 3)

    result = repo.add_import(acct, rec, [a, a_dup, b, c])
    assert result.new_trades == 3
    assert result.duplicate_trades == 1
    # All three distinct trades are persisted under this import_id.
    assert {row.ticker for row in repo.trades_for_import(result.import_id)} == {"TSLA", "AAPL", "MSFT"}


def test_existing_db_dup_does_not_drop_neighbors(repo):
    """Same protection when the duplicate hits an EXISTING DB row (not just
    a within-batch sibling) — pre-fix code rollback-cascaded these too.
    """
    acct = repo.get_or_create_account("schwab", "personal")
    rec1 = ImportRecord(
        account_id=acct.id, csv_filename="a.csv", csv_sha256="h1", imported_at=datetime(2026, 4, 25), trade_count=0
    )
    seed = _trade(acct.display(), "TSLA", 10)
    repo.add_import(acct, rec1, [seed])

    rec2 = ImportRecord(
        account_id=acct.id, csv_filename="b.csv", csv_sha256="h2", imported_at=datetime(2026, 4, 26), trade_count=0
    )
    fresh_a = _trade(acct.display(), "AAPL", 5)
    seed_again = _trade(acct.display(), "TSLA", 10)  # natural-key collision with rec1
    fresh_b = _trade(acct.display(), "MSFT", 3)

    result = repo.add_import(acct, rec2, [fresh_a, seed_again, fresh_b])
    assert result.new_trades == 2
    assert result.duplicate_trades == 1
    assert {row.ticker for row in repo.trades_for_import(result.import_id)} == {"AAPL", "MSFT"}


def test_add_import_roundtrips_is_section_1256(repo):
    """Regression: is_section_1256 must round-trip through add_import → all_trades."""
    acct = repo.get_or_create_account("schwab", "personal")
    rec = ImportRecord(
        account_id=acct.id,
        csv_filename="s1256.csv",
        csv_sha256="h_s1256",
        imported_at=datetime(2026, 4, 25),
        trade_count=0,
    )
    spx_trade = Trade(
        date=date(2024, 9, 15),
        account=acct.display(),
        ticker="SPX",
        action="Sell",
        quantity=1,
        proceeds=Decimal("100"),
        cost_basis=Decimal("100"),
        option_details=OptionDetails(strike=4500, expiry=date(2025, 12, 19), call_put="C"),
        is_section_1256=True,
    )
    aapl_trade = Trade(
        date=date(2024, 9, 15),
        account=acct.display(),
        ticker="AAPL",
        action="Buy",
        quantity=10,
        proceeds=Decimal("1000"),
        cost_basis=Decimal("1000"),
        option_details=None,
        is_section_1256=False,
    )
    repo.add_import(acct, rec, [spx_trade, aapl_trade])
    loaded = repo.all_trades()
    by_ticker = {t.ticker: t for t in loaded}
    assert by_ticker["SPX"].is_section_1256 is True
    assert by_ticker["AAPL"].is_section_1256 is False
