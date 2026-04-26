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


def test_replace_lots_in_window_persists_lots_from_detection(repo):
    a = repo.get_or_create_account("schwab", "personal")
    rec = ImportRecord(
        account_id=a.id,
        csv_filename="x.csv",
        csv_sha256="h",
        imported_at=datetime(2026, 4, 25),
        trade_count=0,
    )
    trades = [
        Trade(account=a.display(), date=date(2024, 6, 5), ticker="TSLA", action="Buy", quantity=10, cost_basis=1700.0),
        Trade(account=a.display(), date=date(2024, 6, 15), ticker="AAPL", action="Buy", quantity=5, cost_basis=750.0),
    ]
    repo.add_import(a, rec, trades)

    # No lots yet
    assert repo.all_lots() == []

    # Run engine + persist
    window_trades = repo.trades_in_window(date(2024, 5, 1), date(2024, 7, 15))
    result = detect_in_window(window_trades, date(2024, 5, 1), date(2024, 7, 15), etf_pairs={})
    repo.replace_lots_in_window(date(2024, 5, 1), date(2024, 7, 15), result.lots)

    lots = repo.all_lots()
    assert len(lots) == 2
    tickers = {lot.ticker for lot in lots}
    assert tickers == {"TSLA", "AAPL"}


def test_replace_lots_in_window_clears_old_in_window_first(repo):
    a = repo.get_or_create_account("schwab", "personal")
    rec = ImportRecord(
        account_id=a.id,
        csv_filename="x.csv",
        csv_sha256="h",
        imported_at=datetime(2026, 4, 25),
        trade_count=0,
    )
    repo.add_import(
        a,
        rec,
        [
            Trade(
                account=a.display(), date=date(2024, 6, 5), ticker="TSLA", action="Buy", quantity=10, cost_basis=1700.0
            ),
        ],
    )
    window_trades = repo.trades_in_window(date(2024, 5, 1), date(2024, 7, 1))
    result = detect_in_window(window_trades, date(2024, 5, 1), date(2024, 7, 1), etf_pairs={})
    repo.replace_lots_in_window(date(2024, 5, 1), date(2024, 7, 1), result.lots)
    assert len(repo.all_lots()) == 1

    # Run again with same data — count must stay 1, not double
    repo.replace_lots_in_window(date(2024, 5, 1), date(2024, 7, 1), result.lots)
    assert len(repo.all_lots()) == 1


def test_replace_lots_in_window_does_not_touch_lots_outside_window(repo):
    a = repo.get_or_create_account("schwab", "personal")
    rec = ImportRecord(
        account_id=a.id,
        csv_filename="x.csv",
        csv_sha256="h",
        imported_at=datetime(2026, 4, 25),
        trade_count=0,
    )
    repo.add_import(
        a,
        rec,
        [
            Trade(
                account=a.display(),
                date=date(2024, 1, 1),
                ticker="OUT_OF_WIN",
                action="Buy",
                quantity=5,
                cost_basis=100.0,
            ),
            Trade(
                account=a.display(), date=date(2024, 6, 5), ticker="IN_WIN", action="Buy", quantity=10, cost_basis=200.0
            ),
        ],
    )
    # Persist all lots first (full window)
    all_trades = repo.all_trades()
    full_result = detect_in_window(all_trades, date(2024, 1, 1), date(2024, 12, 31), etf_pairs={})
    repo.replace_lots_in_window(date(2024, 1, 1), date(2024, 12, 31), full_result.lots)
    assert len(repo.all_lots()) == 2

    # Now replace ONLY the lots in [2024-05-01, 2024-07-01] — should leave Jan 1 lot alone
    window_trades = repo.trades_in_window(date(2024, 5, 1), date(2024, 7, 1))
    win_result = detect_in_window(window_trades, date(2024, 5, 1), date(2024, 7, 1), etf_pairs={})
    repo.replace_lots_in_window(date(2024, 5, 1), date(2024, 7, 1), win_result.lots)
    lots = repo.all_lots()
    assert len(lots) == 2  # Jan 1 lot preserved
    assert {lot.ticker for lot in lots} == {"OUT_OF_WIN", "IN_WIN"}
