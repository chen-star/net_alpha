"""Schwab re-export with a populated ``Cost Basis`` column must not duplicate sells.

Regression for the I3 bug: ``compute_natural_key`` includes ``cost_basis``.
The first import had no ``Cost Basis`` column (so ``cost_basis=None`` on
the parsed Sell). A later re-export that gains a populated ``Cost Basis``
column produces ``cost_basis=Y`` on the same logical sell — different
natural key, so the second row inserts as a "new" trade. Result: realized
P&L doubles for every re-imported sell.

The fix has to ensure that the import pipeline drops a Sell whose
(account, ticker, date, qty, proceeds) match an existing Sell, regardless
of whether ``cost_basis`` was added in the meantime.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlmodel import SQLModel, create_engine

from net_alpha.brokers.schwab import SchwabParser
from net_alpha.db.repository import Repository
from net_alpha.ingest.dedup import filter_new, filter_sell_basis_drift_duplicates
from net_alpha.models.domain import ImportRecord


@pytest.fixture
def repo(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/reimport.db")
    SQLModel.metadata.create_all(eng)
    return Repository(eng)


_FIRST_EXPORT_ROWS = [
    {
        "Date": "08/01/2024",
        "Action": "Buy",
        "Symbol": "TSLA",
        "Quantity": "10",
        "Price": "$200.00",
        "Amount": "-$2000.00",
    },
    {
        "Date": "09/15/2024",
        "Action": "Sell",
        "Symbol": "TSLA",
        "Quantity": "10",
        "Price": "$240.00",
        "Amount": "$2400.00",
    },
]

# Same data, but Schwab now also emits a ``Cost Basis`` column populated
# for the Sell row. The Buy is identical.
_REEXPORT_ROWS = [
    {
        "Date": "08/01/2024",
        "Action": "Buy",
        "Symbol": "TSLA",
        "Quantity": "10",
        "Price": "$200.00",
        "Amount": "-$2000.00",
        "Cost Basis": "",
    },
    {
        "Date": "09/15/2024",
        "Action": "Sell",
        "Symbol": "TSLA",
        "Quantity": "10",
        "Price": "$240.00",
        "Amount": "$2400.00",
        "Cost Basis": "$2000.00",
    },
]


def test_reimport_with_cost_basis_does_not_duplicate_sell(repo):
    """The same logical Sell, re-imported once the broker added a Cost Basis
    column, must NOT insert a second row."""
    parser = SchwabParser()
    acct = repo.get_or_create_account("schwab", "personal")

    first = parser.parse(_FIRST_EXPORT_ROWS, account_display=acct.display())
    rec1 = ImportRecord(
        account_id=acct.id,
        csv_filename="first.csv",
        csv_sha256="sha1",
        imported_at=datetime(2024, 9, 16),
        trade_count=len(first),
    )
    repo.add_import(acct, rec1, first)
    assert len([t for t in repo.all_trades() if t.action == "Sell"]) == 1

    second = parser.parse(_REEXPORT_ROWS, account_display=acct.display())
    # Mirror the route pipeline: filter_new → filter_sell_basis_drift_duplicates.
    existing = repo.existing_natural_keys(acct.id)
    new_trades = filter_new(second, existing)
    new_trades = filter_sell_basis_drift_duplicates(
        new_trades, existing_keys=repo.existing_sell_basis_blind_keys(acct.id)
    )
    rec2 = ImportRecord(
        account_id=acct.id,
        csv_filename="reexport.csv",
        csv_sha256="sha2",
        imported_at=datetime(2024, 9, 17),
        trade_count=len(new_trades),
    )
    repo.add_import(acct, rec2, new_trades)

    sells = [t for t in repo.all_trades() if t.action == "Sell"]
    assert len(sells) == 1, "re-import added a duplicate sell — natural_key drifted on Cost Basis"
