"""Tax-helper repository methods must exclude tax-advantaged accounts.

Regression for the C1 bug: when ``accounts=None`` (the "All accounts" UI
state), the tax-focused helpers were silently aggregating realized P&L
from IRA / Roth / 401(k) / HSA accounts into the taxable total — so the
Tax page reported a tax bill on non-taxable gains, and the harvest queue
suggested harvesting losses inside a Roth.

The fix is for these helpers to *always* exclude tax-advantaged accounts
regardless of the ``accounts`` filter value. Explicitly filtering on a
tax-advantaged account from the UI returns empty totals (they aren't
taxable events).
"""

from __future__ import annotations

import datetime as dt
from datetime import datetime
from decimal import Decimal

import pytest
from sqlmodel import Session, SQLModel, create_engine

import net_alpha.db.tables  # noqa: F401 — register SQLModel metadata
from net_alpha.db.migrations import migrate
from net_alpha.db.repository import Repository
from net_alpha.db.tables import (
    ImportRecordRow,
    RealizedGLLotRow,
    Section1256ClassificationRow,
    TradeRow,
)
from net_alpha.models.domain import Section1256MTM
from net_alpha.portfolio.after_tax import Period


@pytest.fixture()
def repo(tmp_path):
    """Two accounts: ``Schwab/Taxable`` and ``Schwab/Roth`` (type=roth_ira)."""
    engine = create_engine(f"sqlite:///{tmp_path}/taxable_only.db")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        migrate(session)
    r = Repository(engine)
    r.get_or_create_account("Schwab", "Taxable")
    r.get_or_create_account("Schwab", "Roth")
    r.set_account_type(broker="Schwab", label="Roth", type_="roth_ira")
    return r


def _seed_realized_gl(repo: Repository, *, acct_display: str, pnl: Decimal, year: int = 2025) -> None:
    broker, label = acct_display.split("/", 1)
    acct = repo.get_account(broker, label)
    assert acct is not None
    with Session(repo.engine) as s:
        imp = ImportRecordRow(
            account_id=acct.id,
            csv_filename=f"gl_{acct_display}.csv",
            csv_sha256=f"sha_{acct_display}_{year}",
            imported_at=datetime(year, 1, 1, 0, 0, 0),
            trade_count=1,
        )
        s.add(imp)
        s.flush()
        proceeds = Decimal("1000") + pnl
        s.add(
            RealizedGLLotRow(
                import_id=imp.id,
                account_id=acct.id,
                symbol_raw="TSLA",
                ticker="TSLA",
                closed_date=f"{year}-06-15",
                opened_date=f"{year}-01-10",
                quantity=10.0,
                proceeds=float(proceeds),
                cost_basis=1000.0,
                unadjusted_cost_basis=1000.0,
                wash_sale=False,
                disallowed_loss=0.0,
                term="Short Term",
                natural_key=f"tsla_{acct_display}_{year}",
            )
        )
        s.commit()


def _seed_section_1256_classification(
    repo: Repository, *, acct_display: str, realized_pnl: Decimal, year: int = 2025
) -> None:
    broker, label = acct_display.split("/", 1)
    acct = repo.get_account(broker, label)
    assert acct is not None
    with Session(repo.engine) as s:
        trade = TradeRow(
            account_id=acct.id,
            natural_key=f"spx_{acct_display}_{year}",
            ticker="SPX",
            trade_date=f"{year}-11-01",
            action="Sell",
            quantity=1.0,
            proceeds=float(Decimal("500") + realized_pnl),
            cost_basis=500.0,
            is_section_1256=True,
        )
        s.add(trade)
        s.flush()
        lt = (realized_pnl * Decimal("3") / Decimal("5")).quantize(Decimal("0.01"))
        st = realized_pnl - lt
        s.add(
            Section1256ClassificationRow(
                trade_id=trade.id,
                realized_pnl=realized_pnl,
                long_term_portion=lt,
                short_term_portion=st,
                underlying="SPX",
            )
        )
        s.commit()


def _mtm_row(account: str, key_suffix: str, year: int = 2025) -> Section1256MTM:
    return Section1256MTM(
        position_key=f"SPX|4000.0|{year}-12-31|C|{key_suffix}",
        tax_year=year,
        last_business_day=dt.date(year, 12, 31),
        fmv=Decimal("150"),
        basis_before=Decimal("100"),
        unrealized_pnl=Decimal("50"),
        long_term_portion=Decimal("30"),
        short_term_portion=Decimal("20"),
        fmv_source="yahoo",
        ticker="SPX",
        account=account,
    )


# ---------------------------------------------------------------------------
# realized_pnl_split: Roth gains must NOT leak into the taxable total.
# ---------------------------------------------------------------------------


def test_realized_pnl_split_excludes_roth_when_no_account_filter(repo):
    _seed_realized_gl(repo, acct_display="Schwab/Taxable", pnl=Decimal("200"))
    _seed_realized_gl(repo, acct_display="Schwab/Roth", pnl=Decimal("500"))

    result = repo.realized_pnl_split(Period.for_year(2025))

    # Only the taxable account counts. Without the fix the Roth $500 leaks in.
    assert result["short_term"] == Decimal("200")
    assert result["long_term"] == Decimal("0")


def test_realized_pnl_split_explicit_roth_filter_returns_zero(repo):
    _seed_realized_gl(repo, acct_display="Schwab/Taxable", pnl=Decimal("200"))
    _seed_realized_gl(repo, acct_display="Schwab/Roth", pnl=Decimal("500"))

    result = repo.realized_pnl_split(Period.for_year(2025), accounts=["Schwab/Roth"])

    # The Roth isn't a taxable event — even if the UI explicitly filters to
    # it, the after-tax helper returns 0 (not the $500 gain).
    assert result == {"short_term": Decimal("0"), "long_term": Decimal("0")}


def test_realized_pnl_split_mixed_filter_keeps_only_taxable(repo):
    _seed_realized_gl(repo, acct_display="Schwab/Taxable", pnl=Decimal("200"))
    _seed_realized_gl(repo, acct_display="Schwab/Roth", pnl=Decimal("500"))

    result = repo.realized_pnl_split(Period.for_year(2025), accounts=["Schwab/Taxable", "Schwab/Roth"])
    assert result["short_term"] == Decimal("200")


# ---------------------------------------------------------------------------
# section_1256_pnl: §1256 gain inside a Roth is not a taxable event.
# ---------------------------------------------------------------------------


def test_section_1256_pnl_excludes_roth_when_no_account_filter(repo):
    _seed_section_1256_classification(repo, acct_display="Schwab/Taxable", realized_pnl=Decimal("1000"))
    _seed_section_1256_classification(repo, acct_display="Schwab/Roth", realized_pnl=Decimal("2000"))

    total = repo.section_1256_pnl(Period.for_year(2025))
    assert total == Decimal("1000")


# ---------------------------------------------------------------------------
# section_1256_mtm_pnl: year-end mark-to-market in a Roth doesn't tax.
# ---------------------------------------------------------------------------


def test_section_1256_mtm_pnl_excludes_roth_when_no_account_filter(repo):
    repo.save_section_1256_mtm([_mtm_row("Schwab/Taxable", "k_t"), _mtm_row("Schwab/Roth", "k_r")])

    total = repo.section_1256_mtm_pnl(Period.for_year(2025))
    # Each row carries unrealized_pnl=50; only the taxable row should count.
    assert total == Decimal("50")
