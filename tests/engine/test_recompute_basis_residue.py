"""When merge_violations drops an engine-detected wash sale (e.g. Schwab's
Realized G/L says wash_sale=False on the same loss + same account), the
replacement lot's adjusted_basis must NOT carry the bump the detector
provisionally applied. Otherwise the lot accumulates stale residue across
recompute cycles — the source of dozens of phantom BasisRecon FAIL findings.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlmodel import SQLModel, create_engine

from net_alpha.db.repository import Repository
from net_alpha.engine.recompute import recompute_all_violations
from net_alpha.models.domain import ImportRecord, Trade
from net_alpha.models.realized_gl import RealizedGLLot


@pytest.fixture
def repo(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/basis_residue.db")
    SQLModel.metadata.create_all(eng)
    return Repository(eng)


def _seed_loss_and_repurchase(repo: Repository):
    taxable = repo.get_or_create_account("schwab", "personal")
    rec = ImportRecord(
        account_id=taxable.id,
        csv_filename="t.csv",
        csv_sha256="ht",
        imported_at=datetime(2025, 9, 30),
        trade_count=0,
    )
    buy_pre = Trade(
        account=taxable.display(),
        date=date(2025, 6, 1),
        ticker="BKSY",
        action="Buy",
        quantity=10,
        cost_basis=200.0,  # $20/share
    )
    sell_loss = Trade(
        account=taxable.display(),
        date=date(2025, 8, 1),
        ticker="BKSY",
        action="Sell",
        quantity=10,
        proceeds=100.0,  # loss of $100
        cost_basis=200.0,
    )
    buy_replace = Trade(
        account=taxable.display(),
        date=date(2025, 8, 15),  # within ±30 → wash-sale trigger
        ticker="BKSY",
        action="Buy",
        quantity=4,
        cost_basis=75.52,
    )
    repo.add_import(taxable, rec, [buy_pre, sell_loss, buy_replace])
    return taxable


def test_engine_violation_kept_bumps_lot_basis(repo):
    """Sanity baseline: when no G/L override, engine violation survives and
    the replacement lot's adjusted_basis IS bumped. (Confirms the fix
    doesn't accidentally suppress legitimate rollovers.)"""
    _seed_loss_and_repurchase(repo)
    recompute_all_violations(repo, etf_pairs={})

    violations = repo.all_violations()
    assert len(violations) == 1
    # The disallowed loss flows into the replacement lot's adjusted_basis.
    replacement_lot = next(lot for lot in repo.all_lots() if lot.ticker == "BKSY" and lot.date == date(2025, 8, 15))
    assert replacement_lot.adjusted_basis > replacement_lot.cost_basis


def test_merge_dropped_violation_leaves_no_basis_residue(repo):
    """The bug: Schwab G/L says wash_sale=False for the loss → merge drops
    the engine violation → replacement lot's adjusted_basis must reset to
    cost_basis. Pre-fix it carried a stale bump."""
    taxable = _seed_loss_and_repurchase(repo)

    # Schwab Realized G/L row asserting wash_sale=False on the loss leg.
    # merge_violations rule 2a: same-account exact-ticker match + Schwab No
    # → drop the engine violation.
    repo.add_gl_lots(
        taxable,
        import_id=1,
        lots=[
            RealizedGLLot(
                account_display=taxable.display(),
                symbol_raw="BKSY",
                ticker="BKSY",
                closed_date=date(2025, 8, 1),
                opened_date=date(2025, 6, 1),
                quantity=10,
                proceeds=100.0,
                cost_basis=200.0,
                unadjusted_cost_basis=200.0,
                wash_sale=False,
                disallowed_loss=0.0,
                term="Short Term",
            )
        ],
    )
    recompute_all_violations(repo, etf_pairs={})

    # Engine emitted a violation, merge dropped it.
    violations = repo.all_violations()
    assert violations == []

    # And the replacement lot must NOT have the dropped bump baked in.
    replacement_lot = next(lot for lot in repo.all_lots() if lot.ticker == "BKSY" and lot.date == date(2025, 8, 15))
    assert replacement_lot.adjusted_basis == replacement_lot.cost_basis, (
        f"stale residue: adjusted_basis={replacement_lot.adjusted_basis} cost_basis={replacement_lot.cost_basis}"
    )
