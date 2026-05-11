"""ST/LT classification honors per-lot FIFO matching and §1223(4) tacking.

``realized_pnl_split_by_year`` previously used the earliest buy date for the
ticker regardless of which lot the sell actually consumed. After the fix:
the sell is FIFO-matched to a lot, and that lot's ``effective_acquired_date``
(which respects wash-sale tacking) drives ST/LT classification.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

from net_alpha.db.migrations import migrate
from net_alpha.db.repository import Repository
from net_alpha.db.tables import AccountRow, LotRow, TradeRow


@pytest.fixture
def repo() -> Repository:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        migrate(s)
        acct = AccountRow(broker="schwab", label="taxable")
        s.add(acct)
        s.commit()
        s.refresh(acct)
        s._acct_id = acct.id
    return Repository(engine)


def _insert_trade(
    repo: Repository,
    *,
    account_id: int,
    trade_date: date,
    action: str,
    quantity: float,
    proceeds: float | None = None,
    cost_basis: float | None = None,
    ticker: str = "AAPL",
) -> int:
    with Session(repo.engine) as s:
        row = TradeRow(
            account_id=account_id,
            trade_date=trade_date.isoformat(),
            ticker=ticker,
            action=action,
            quantity=quantity,
            proceeds=proceeds,
            cost_basis=cost_basis,
            import_id=None,
            natural_key=f"{trade_date.isoformat()}|{action}|{quantity}|{proceeds}|{cost_basis}",
            basis_unknown=False,
            basis_source="schwab_csv",
        )
        s.add(row)
        s.commit()
        s.refresh(row)
        return row.id


def _insert_lot(
    repo: Repository,
    *,
    trade_id: int,
    account_id: int,
    trade_date: date,
    quantity: float,
    cost_basis: float,
    adjusted_basis: float | None = None,
    tacked_acquired_date: date | None = None,
    ticker: str = "AAPL",
) -> None:
    with Session(repo.engine) as s:
        row = LotRow(
            trade_id=trade_id,
            account_id=account_id,
            ticker=ticker,
            trade_date=trade_date.isoformat(),
            quantity=quantity,
            cost_basis=cost_basis,
            adjusted_basis=adjusted_basis if adjusted_basis is not None else cost_basis,
            tacked_acquired_date=(tacked_acquired_date.isoformat() if tacked_acquired_date else None),
        )
        s.add(row)
        s.commit()


def _get_account_id(repo: Repository) -> int:
    with Session(repo.engine) as s:
        return s.exec(SQLModel.metadata.tables["accounts"].select()).first()[0]


def test_tacked_acquired_date_promotes_st_to_lt(repo: Repository):
    """A sale held 198 days raw but tacked back >2 years is classified LT."""
    acct = _get_account_id(repo)

    # Only the replacement buy exists in the chain (the original loss-side
    # lot has been disposed of in a prior year; its row has quantity 0 below
    # is omitted here to keep the chain singular).
    replacement_buy_id = _insert_trade(
        repo,
        account_id=acct,
        trade_date=date(2024, 8, 1),
        action="Buy",
        quantity=10.0,
        cost_basis=900.0,
    )
    _insert_lot(
        repo,
        trade_id=replacement_buy_id,
        account_id=acct,
        trade_date=date(2024, 8, 1),
        quantity=10.0,
        cost_basis=900.0,
        adjusted_basis=1100.0,
        tacked_acquired_date=date(2023, 1, 1),
    )

    # Sell on 2025-02-15: 198 days after replacement buy (raw → ST), but
    # tacked back to 2023-01-01 → >2 years → LT.
    _insert_trade(
        repo,
        account_id=acct,
        trade_date=date(2025, 2, 15),
        action="Sell",
        quantity=10.0,
        proceeds=1500.0,
        cost_basis=1100.0,
    )

    st, lt = repo.realized_pnl_split_by_year(2025)
    # P&L = 1500 - 1100 = 400. With tacking → LT.
    assert lt == Decimal("400")
    assert st == Decimal("0")


def test_fifo_consumes_correct_lot_for_classification(repo: Repository):
    """When two lots exist, the sell consumes the FIFO-earliest; classification
    uses *that* lot's effective acquired date, not the earliest ever buy."""
    acct = _get_account_id(repo)

    # Buy 1: 2023-01-01 — already sold (consumed by a prior sale in 2024).
    b1_id = _insert_trade(
        repo,
        account_id=acct,
        trade_date=date(2023, 1, 1),
        action="Buy",
        quantity=10.0,
        cost_basis=1000.0,
    )
    _insert_lot(
        repo,
        trade_id=b1_id,
        account_id=acct,
        trade_date=date(2023, 1, 1),
        quantity=0.0,
        cost_basis=1000.0,
    )

    # Prior sell on 2024-06-01 consumed b1 fully (10 shares).
    _insert_trade(
        repo,
        account_id=acct,
        trade_date=date(2024, 6, 1),
        action="Sell",
        quantity=10.0,
        proceeds=1300.0,
        cost_basis=1000.0,
    )

    # Buy 2: 2024-12-01 — 10 shares, no tacking.
    b2_id = _insert_trade(
        repo,
        account_id=acct,
        trade_date=date(2024, 12, 1),
        action="Buy",
        quantity=10.0,
        cost_basis=1100.0,
    )
    _insert_lot(
        repo,
        trade_id=b2_id,
        account_id=acct,
        trade_date=date(2024, 12, 1),
        quantity=10.0,
        cost_basis=1100.0,
    )

    # Sell on 2025-03-01 — only b2 is available (b1 already consumed). Days
    # held from b2 = 90 → ST. Before fix this would have used b1's date
    # (~790 days) and misclassified as LT.
    _insert_trade(
        repo,
        account_id=acct,
        trade_date=date(2025, 3, 1),
        action="Sell",
        quantity=10.0,
        proceeds=1400.0,
        cost_basis=1100.0,
    )

    st, lt = repo.realized_pnl_split_by_year(2025)
    # P&L = 1400 - 1100 = 300. From b2 (90 days held) → ST.
    assert st == Decimal("300")
    assert lt == Decimal("0")
