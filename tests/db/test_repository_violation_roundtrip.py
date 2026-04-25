from datetime import date, datetime

import pytest
from sqlmodel import SQLModel, create_engine

from net_alpha.db.repository import Repository
from net_alpha.engine.detector import detect_in_window
from net_alpha.models.domain import ImportRecord, Trade


@pytest.fixture
def repo(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/v2.db")
    SQLModel.metadata.create_all(eng)
    return Repository(eng)


def _setup_one_violation(repo):
    a = repo.get_or_create_account("schwab", "personal")
    b = repo.get_or_create_account("schwab", "roth")
    rec_a = ImportRecord(
        account_id=a.id, csv_filename="a.csv", csv_sha256="h", imported_at=datetime(2026, 4, 25), trade_count=0
    )
    rec_b = ImportRecord(
        account_id=b.id, csv_filename="b.csv", csv_sha256="h", imported_at=datetime(2026, 4, 25), trade_count=0
    )
    sell = Trade(
        account=a.display(),
        date=date(2024, 6, 1),
        ticker="TSLA",
        action="Sell",
        quantity=10,
        proceeds=1500.0,
        cost_basis=2000.0,
    )
    buy = Trade(account=b.display(), date=date(2024, 6, 5), ticker="TSLA", action="Buy", quantity=10, cost_basis=1700.0)
    repo.add_import(a, rec_a, [sell])
    repo.add_import(b, rec_b, [buy])

    # Run engine and persist
    trades = repo.all_trades()
    violations = detect_in_window(trades, date(2024, 5, 1), date(2024, 7, 1), etf_pairs={}).violations
    repo.replace_violations_in_window(date(2024, 5, 1), date(2024, 7, 1), violations)


def test_all_violations_roundtrip_preserves_account_and_date_fields(repo):
    _setup_one_violation(repo)
    vs = repo.all_violations()
    assert len(vs) == 1
    v = vs[0]
    assert v.loss_sale_date == date(2024, 6, 1)
    assert v.triggering_buy_date == date(2024, 6, 5)
    assert v.loss_account == "schwab/personal"
    assert v.buy_account == "schwab/roth"
    assert v.ticker == "TSLA"
    assert v.confidence == "Confirmed"


def test_violations_for_year_roundtrip_preserves_fields(repo):
    _setup_one_violation(repo)
    vs = repo.violations_for_year(2024)
    assert len(vs) == 1
    assert vs[0].loss_account == "schwab/personal"
    assert vs[0].buy_account == "schwab/roth"
    assert vs[0].loss_sale_date == date(2024, 6, 1)
    assert vs[0].triggering_buy_date == date(2024, 6, 5)
