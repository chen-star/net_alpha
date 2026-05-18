"""``realized_pnl_split_by_year`` must add back wash-disallowed losses.

Regression for the C2 bug: the carryforward derivation was using raw
economic P&L (``sell.proceeds - sell.cost_basis``) from the trade row,
which is the *pre-wash* basis. When a wash sale disallows part of the
loss, that portion is not deductible in the current year and instead
rolls into the replacement lot's basis. Without the add-back, the
loss is double-relieved: once as a current-year carryforward and again
as basis when the replacement lot is later sold.

Same-year ``realized_pnl_split`` already reads from
``RealizedGLLotRow.cost_basis`` (broker's wash-adjusted basis) — the
two functions diverged.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlmodel import SQLModel, create_engine

from net_alpha.db.repository import Repository
from net_alpha.engine.recompute import recompute_all_violations
from net_alpha.models.domain import ImportRecord, Trade


@pytest.fixture
def repo(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/wash_carryforward.db")
    SQLModel.metadata.create_all(eng)
    return Repository(eng)


def test_wash_disallowed_loss_is_added_back_to_year_pnl(repo):
    """A deferred §1091(d) wash sale must not show up in the year's carryforward.

    Scenario:
      - Buy 10 TSLA @ 200 on 2024-01-10 (basis = $2000)
      - Sell 10 TSLA @ 150 on 2024-06-01 (proceeds = $1500, economic loss = -$500)
      - Re-buy 10 TSLA @ 170 on 2024-06-05 (within 30 days → §1091 wash)
      - Engine disallows the full $500 loss and rolls it into the replacement
        lot's basis.

    The carryforward derive must see *tax-recognized* P&L of $0 for this
    sell (loss disallowed), NOT economic P&L of -$500.
    """
    taxable = repo.get_or_create_account("schwab", "personal")
    rec = ImportRecord(
        account_id=taxable.id,
        csv_filename="t.csv",
        csv_sha256="h_t",
        imported_at=datetime(2024, 12, 31),
        trade_count=0,
    )
    trades = [
        Trade(
            account=taxable.display(),
            date=date(2024, 1, 10),
            ticker="TSLA",
            action="Buy",
            quantity=10,
            proceeds=None,
            cost_basis=2000.0,
        ),
        Trade(
            account=taxable.display(),
            date=date(2024, 6, 1),
            ticker="TSLA",
            action="Sell",
            quantity=10,
            proceeds=1500.0,
            cost_basis=2000.0,
        ),
        Trade(
            account=taxable.display(),
            date=date(2024, 6, 5),
            ticker="TSLA",
            action="Buy",
            quantity=10,
            proceeds=None,
            cost_basis=1700.0,
        ),
    ]
    repo.add_import(taxable, rec, trades)
    recompute_all_violations(repo, etf_pairs={})

    # Sanity: wash-sale engine recognized the deferred violation.
    violations = repo.all_violations()
    assert len(violations) == 1
    assert violations[0].disallowed_loss == pytest.approx(500.0)

    st, lt = repo.realized_pnl_split_by_year(2024)

    # Tax-recognized loss is $0 (the full $500 was disallowed). Without the
    # fix this comes back as -$500 (economic loss leaks into carryforward).
    assert st == Decimal("0")
    assert lt == Decimal("0")


def test_partial_wash_disallowed_partial_loss_remains(repo):
    """When only part of a loss is disallowed, the rest must remain on the books.

    Sell 10 TSLA at a $500 loss; only 4 shares get rebought within ±30 days
    so only 40% of the loss ($200) is disallowed. The carryforward should
    see ``economic_loss + disallowed = -500 + 200 = -300``.
    """
    taxable = repo.get_or_create_account("schwab", "personal")
    rec = ImportRecord(
        account_id=taxable.id,
        csv_filename="t.csv",
        csv_sha256="h_t",
        imported_at=datetime(2024, 12, 31),
        trade_count=0,
    )
    trades = [
        Trade(
            account=taxable.display(),
            date=date(2024, 1, 10),
            ticker="TSLA",
            action="Buy",
            quantity=10,
            proceeds=None,
            cost_basis=2000.0,
        ),
        Trade(
            account=taxable.display(),
            date=date(2024, 6, 1),
            ticker="TSLA",
            action="Sell",
            quantity=10,
            proceeds=1500.0,
            cost_basis=2000.0,
        ),
        Trade(
            account=taxable.display(),
            date=date(2024, 6, 5),
            ticker="TSLA",
            action="Buy",
            quantity=4,
            proceeds=None,
            cost_basis=680.0,
        ),
    ]
    repo.add_import(taxable, rec, trades)
    recompute_all_violations(repo, etf_pairs={})

    violations = repo.all_violations()
    assert len(violations) == 1
    assert violations[0].disallowed_loss == pytest.approx(200.0)

    st, lt = repo.realized_pnl_split_by_year(2024)

    # -500 economic + 200 disallowed add-back = -300 tax-recognized loss.
    assert st == Decimal("-300")
    assert lt == Decimal("0")


def test_no_wash_sale_unchanged(repo):
    """Sanity: when no wash sale exists, behavior matches the prior version."""
    taxable = repo.get_or_create_account("schwab", "personal")
    rec = ImportRecord(
        account_id=taxable.id,
        csv_filename="t.csv",
        csv_sha256="h_t",
        imported_at=datetime(2024, 12, 31),
        trade_count=0,
    )
    trades = [
        Trade(
            account=taxable.display(),
            date=date(2024, 1, 10),
            ticker="TSLA",
            action="Buy",
            quantity=10,
            proceeds=None,
            cost_basis=2000.0,
        ),
        Trade(
            account=taxable.display(),
            date=date(2024, 6, 1),
            ticker="TSLA",
            action="Sell",
            quantity=10,
            proceeds=1500.0,
            cost_basis=2000.0,
        ),
    ]
    repo.add_import(taxable, rec, trades)
    recompute_all_violations(repo, etf_pairs={})

    assert repo.all_violations() == []
    st, lt = repo.realized_pnl_split_by_year(2024)
    assert st == Decimal("-500")
    assert lt == Decimal("0")
