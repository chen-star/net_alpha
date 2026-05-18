"""Harvest queue must exclude open losses inside tax-advantaged accounts.

Regression for the C1 bug: ``_open_lots_with_loss`` (the candidate source
for ``compute_harvest_queue``) only filtered by ``account_id``, so when
no account was selected in the UI it surfaced loss lots inside a Roth /
Traditional IRA / 401(k) / HSA — none of which yield any tax benefit
from harvesting. The fix is to skip lots whose account type is anything
other than ``taxable``.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlmodel import SQLModel, create_engine

from net_alpha.db.repository import Repository
from net_alpha.engine.recompute import recompute_all_violations
from net_alpha.models.domain import ImportRecord, Trade
from net_alpha.portfolio.tax_planner import compute_harvest_queue


@pytest.fixture
def repo(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/harvest_taxadv.db")
    SQLModel.metadata.create_all(eng)
    return Repository(eng)


def _seed_open_loss(repo: Repository, account_label: str, account_type: str) -> str:
    """Plant a single open buy lot whose market price is below basis."""
    acct = repo.get_or_create_account("schwab", account_label)
    if account_type != "taxable":
        repo.set_account_type(broker="schwab", label=account_label, type_=account_type)
    rec = ImportRecord(
        account_id=acct.id,
        csv_filename=f"{account_label}.csv",
        csv_sha256=f"h_{account_label}",
        imported_at=datetime(2024, 1, 1),
        trade_count=0,
    )
    buy = Trade(
        account=acct.display(),
        date=date(2024, 1, 10),
        ticker="TSLA",
        action="Buy",
        quantity=10,
        proceeds=None,
        cost_basis=2000.0,
    )
    repo.add_import(acct, rec, [buy])
    return acct.display()


def _pricing_stub(price: Decimal) -> MagicMock:
    """Mock PricingService returning a constant quote for any symbol."""
    p = MagicMock()
    quote = MagicMock()
    quote.price = price
    p.get_prices = lambda symbols: {s: quote for s in symbols}
    return p


def test_compute_harvest_queue_excludes_roth_when_no_account_filter(repo):
    _seed_open_loss(repo, account_label="personal", account_type="taxable")
    _seed_open_loss(repo, account_label="roth", account_type="roth_ira")
    recompute_all_violations(repo, etf_pairs={})  # populate the lots table
    pricing = _pricing_stub(Decimal("150"))  # below basis $200/share

    rows = compute_harvest_queue(
        repo=repo,
        pricing=pricing,
        as_of=date(2024, 6, 1),
        etf_pairs={},
        etf_replacements={},
        account_id=None,
    )

    # Only the taxable open loss should be a harvest candidate.
    labels = {r.account_label for r in rows}
    assert labels == {"schwab/personal"}


@pytest.mark.parametrize("tax_advantaged_type", ["roth_ira", "trad_ira", "401k", "hsa"])
def test_compute_harvest_queue_skips_each_tax_advantaged_type(repo, tax_advantaged_type):
    _seed_open_loss(repo, account_label="taxadv", account_type=tax_advantaged_type)
    recompute_all_violations(repo, etf_pairs={})  # populate the lots table
    pricing = _pricing_stub(Decimal("150"))

    rows = compute_harvest_queue(
        repo=repo,
        pricing=pricing,
        as_of=date(2024, 6, 1),
        etf_pairs={},
        etf_replacements={},
        account_id=None,
    )

    assert rows == []
