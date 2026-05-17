"""get_equity_gl_closures + get_option_gl_closures must return quantities
expressed in the *post-split* unit scale so the verify reconciler joins
them against split-adjusted lot.quantity without double-counting.

The SQQQ data in the user's DB has three pre-split GL closures
(2025-08-13: 20, 2025-09-19: 21, 2025-09-22: 20) and one post-split GL
closure (2025-11-21: 0.8). The 1-for-5 reverse split was 2025-11-20.
Pre-fix the helper returned the raw sum 61.8; post-fix it must scale
the pre-split rows: 20*0.2 + 21*0.2 + 20*0.2 + 0.8 = 13.0.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlmodel import SQLModel, create_engine

from net_alpha.db.repository import Repository
from net_alpha.models.realized_gl import RealizedGLLot


@pytest.fixture
def repo(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/gl_splits_test.db")
    SQLModel.metadata.create_all(eng)
    r = Repository(eng)
    r.get_or_create_account("schwab", "st")
    return r


def _seed_split(repo: Repository) -> None:
    repo.add_split(symbol="SQQQ", split_date=date(2025, 11, 20), ratio=0.2, source="yahoo")


def _gl_lot(ticker: str, close: date, qty: float) -> RealizedGLLot:
    return RealizedGLLot(
        account_display="schwab/st",
        symbol_raw=ticker,
        ticker=ticker,
        closed_date=close,
        opened_date=date(2025, 6, 26),
        quantity=qty,
        proceeds=qty * 15.0,
        cost_basis=qty * 20.0,
        unadjusted_cost_basis=qty * 20.0,
        wash_sale=False,
        disallowed_loss=0.0,
        term="Short Term",
    )


def _seed_gl_lots(repo: Repository, lots: list[RealizedGLLot]) -> None:
    account = repo.list_accounts()[0]
    from datetime import datetime as _dt

    from net_alpha.models.domain import ImportRecord

    record = ImportRecord(
        account_id=account.id,
        csv_filename="seed.csv",
        csv_sha256="sha-seed-gl",
        imported_at=_dt.now(),
        trade_count=0,
    )
    import_result = repo.add_import(account, record, [])
    repo.add_gl_lots(account, import_result.import_id, lots)


def test_get_equity_gl_closures_scales_pre_split_rows(repo):
    _seed_split(repo)
    _seed_gl_lots(
        repo,
        [
            _gl_lot("SQQQ", date(2025, 8, 13), 20.0),  # pre-split → ×0.2 = 4.0
            _gl_lot("SQQQ", date(2025, 9, 19), 21.0),  # pre-split → ×0.2 = 4.2
            _gl_lot("SQQQ", date(2025, 9, 22), 20.0),  # pre-split → ×0.2 = 4.0
            _gl_lot("SQQQ", date(2025, 11, 21), 0.8),  # post-split → as-is
        ],
    )

    closures = repo.get_equity_gl_closures()
    # Expected post-split total: 4.0 + 4.2 + 4.0 + 0.8 = 13.0
    assert closures[("schwab/st", "SQQQ")] == pytest.approx(13.0)


def test_get_equity_gl_closures_no_split_is_noop(repo):
    """For tickers with no splits, scaling factor is 1.0."""
    _seed_gl_lots(repo, [_gl_lot("AAPL", date(2025, 9, 22), 20.0)])
    closures = repo.get_equity_gl_closures()
    assert closures[("schwab/st", "AAPL")] == 20.0
