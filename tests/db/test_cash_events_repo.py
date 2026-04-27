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
