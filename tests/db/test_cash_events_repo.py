from datetime import date, datetime

from sqlalchemy import create_engine
from sqlmodel import SQLModel

from net_alpha.db.repository import Repository
from net_alpha.models.domain import CashEvent, ImportRecord


def _setup():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    repo = Repository(engine)
    account = repo.get_or_create_account("Schwab", "short_term")
    rec = ImportRecord(
        id=None,
        account_id=account.id,
        csv_filename="x.csv",
        csv_sha256="abc",
        imported_at=datetime(2026, 4, 26, 12, 0, 0),
        trade_count=0,
    )
    result = repo.add_import(account, rec, trades=[])
    return repo, account, result.import_id


def _ev(d, kind, amount, account="Schwab/short_term", description="x"):
    return CashEvent(
        account=account,
        event_date=d,
        kind=kind,
        amount=amount,
        ticker=None,
        description=description,
    )


def test_add_cash_events_inserts_new_rows():
    repo, _account, import_id = _setup()
    events = [
        _ev(date(2026, 3, 31), "dividend", 4.47, description="SQQQ DIV"),
        _ev(date(2026, 3, 30), "interest", 0.06, description="SCHWAB1 INT"),
    ]
    n = repo.add_cash_events(events, import_id=import_id)
    assert n == 2
    listed = repo.list_cash_events()
    assert len(listed) == 2
    assert {e.kind for e in listed} == {"dividend", "interest"}


def test_add_cash_events_is_idempotent_on_natural_key():
    repo, _account, import_id = _setup()
    events = [_ev(date(2026, 3, 31), "dividend", 4.47, description="SQQQ DIV")]
    repo.add_cash_events(events, import_id=import_id)
    n2 = repo.add_cash_events(events, import_id=import_id)
    assert n2 == 0
    assert len(repo.list_cash_events()) == 1


def test_list_cash_events_filters_by_account_id():
    repo, account, import_id = _setup()
    other = repo.get_or_create_account("Schwab", "long_term")
    other_rec = ImportRecord(
        id=None, account_id=other.id, csv_filename="y.csv", csv_sha256="def",
        imported_at=datetime(2026, 4, 26, 12, 0, 0), trade_count=0,
    )
    other_import = repo.add_import(other, other_rec, trades=[]).import_id
    repo.add_cash_events(
        [_ev(date(2026, 3, 31), "dividend", 1.0, account="Schwab/short_term", description="A")],
        import_id=import_id,
    )
    repo.add_cash_events(
        [_ev(date(2026, 3, 31), "dividend", 2.0, account="Schwab/long_term", description="B")],
        import_id=other_import,
    )
    short = repo.list_cash_events(account_id=account.id)
    long = repo.list_cash_events(account_id=other.id)
    assert {e.amount for e in short} == {1.0}
    assert {e.amount for e in long} == {2.0}


def test_list_cash_events_filters_by_date_range():
    repo, _account, import_id = _setup()
    repo.add_cash_events(
        [
            _ev(date(2025, 12, 31), "dividend", 1.0, description="A"),
            _ev(date(2026, 1, 1), "dividend", 2.0, description="B"),
            _ev(date(2026, 6, 30), "dividend", 3.0, description="C"),
        ],
        import_id=import_id,
    )
    in_2026 = repo.list_cash_events(since=date(2026, 1, 1), until=date(2026, 12, 31))
    assert {e.amount for e in in_2026} == {2.0, 3.0}


def test_remove_import_cascade_deletes_cash_events():
    repo, _account, import_id = _setup()
    repo.add_cash_events(
        [_ev(date(2026, 3, 31), "dividend", 4.47, description="SQQQ DIV")],
        import_id=import_id,
    )
    assert len(repo.list_cash_events()) == 1
    repo.remove_import(import_id)
    assert len(repo.list_cash_events()) == 0
