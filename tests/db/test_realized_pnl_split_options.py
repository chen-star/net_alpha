"""``realized_pnl_split_by_year`` / ``realized_pnl_contributions_by_year`` must
include NON-§1256 option realized P&L (regular equity options — covered calls,
CSPs, long options), sourced from the broker Realized G/L CSV by term.

Regression: these were "equities only", so realized option income silently
vanished from the year-end tax projection and harvest offset budget — even
though it's ordinary capital gain/loss and shows up in the Performance tile
(which reads ``realized_pnl_split``). §1256 broad-index options stay excluded
here (handled separately via 60/40 + MTM)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from sqlmodel import Session, SQLModel, create_engine

from net_alpha.db.repository import Repository
from net_alpha.db.tables import RealizedGLLotRow


@pytest.fixture
def repo(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/opt_pnl.db")
    SQLModel.metadata.create_all(eng)
    return Repository(eng)


def _add_gl_option(repo, *, account_id, import_id, ticker, proceeds, cost, term, strike, closed="2026-03-15"):
    with Session(repo.engine) as s:
        s.add(
            RealizedGLLotRow(
                import_id=import_id,
                account_id=account_id,
                symbol_raw=f"{ticker} {strike}P",
                ticker=ticker,
                closed_date=closed,
                opened_date="2026-01-10",
                quantity=1.0,
                proceeds=proceeds,
                cost_basis=cost,
                unadjusted_cost_basis=cost,
                wash_sale=False,
                disallowed_loss=0.0,
                term=term,
                option_strike=strike,
                option_expiry="2026-06-19",
                natural_key=f"{ticker}_{strike}_{closed}",
            )
        )
        s.commit()


def _setup(repo):
    acct = repo.get_or_create_account("schwab", "personal")
    from net_alpha.models.domain import ImportRecord

    rec = ImportRecord(
        account_id=acct.id,
        csv_filename="gl.csv",
        csv_sha256="h_gl",
        imported_at=datetime(2026, 12, 31),
        trade_count=0,
    )
    res = repo.add_import(acct, rec, [], cash_events=[])
    return acct, res.import_id


def test_split_by_year_includes_non_section1256_option_pnl(repo):
    acct, import_id = _setup(repo)
    # Regular equity option (HIMS put) — ST gain of $650.
    _add_gl_option(
        repo,
        account_id=acct.id,
        import_id=import_id,
        ticker="HIMS",
        proceeds=700.0,
        cost=50.0,
        term="Short Term",
        strike=100.0,
    )
    st, lt = repo.realized_pnl_split_by_year(2026)
    assert st == Decimal("650.0"), f"non-§1256 option ST gain must be included, got {st}"
    assert lt == Decimal("0")


def test_split_by_year_excludes_section1256_option_pnl(repo):
    acct, import_id = _setup(repo)
    # SPX is a §1256 broad-based index — handled via 60/40 + MTM elsewhere,
    # so it must NOT land in the regular ST/LT buckets here.
    _add_gl_option(
        repo,
        account_id=acct.id,
        import_id=import_id,
        ticker="SPX",
        proceeds=700.0,
        cost=50.0,
        term="Short Term",
        strike=4500.0,
    )
    st, lt = repo.realized_pnl_split_by_year(2026)
    assert st == Decimal("0"), f"§1256 option must be excluded from regular ST, got {st}"
    assert lt == Decimal("0")


def test_contributions_reconcile_with_split_when_options_present(repo):
    acct, import_id = _setup(repo)
    _add_gl_option(
        repo,
        account_id=acct.id,
        import_id=import_id,
        ticker="HIMS",
        proceeds=700.0,
        cost=50.0,
        term="Short Term",
        strike=100.0,
    )
    _add_gl_option(
        repo,
        account_id=acct.id,
        import_id=import_id,
        ticker="SOFI",
        proceeds=20.0,
        cost=120.0,
        term="Long Term",
        strike=8.0,
        closed="2026-04-01",
    )
    st, lt = repo.realized_pnl_split_by_year(2026)
    contributions = repo.realized_pnl_contributions_by_year(2026)
    # audit #4 invariant: contributions sum == ST + LT.
    assert sum(contributions, Decimal("0")) == st + lt
    # HIMS +650 ST, SOFI -100 LT.
    assert st == Decimal("650.0")
    assert lt == Decimal("-100.0")
