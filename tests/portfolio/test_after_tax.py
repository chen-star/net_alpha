"""compute_after_tax math correctness, all paths."""

from datetime import datetime
from decimal import Decimal

from sqlmodel import Session, SQLModel, create_engine

import net_alpha.db.tables  # noqa: F401 — register SQLModel metadata
from net_alpha.db.migrations import migrate
from net_alpha.db.repository import Repository
from net_alpha.db.tables import AccountRow, ImportRecordRow, RealizedGLLotRow
from net_alpha.portfolio.after_tax import Period, compute_after_tax
from net_alpha.portfolio.tax_planner import TaxBrackets


def _brackets(*, niit=True, state=Decimal("0")) -> TaxBrackets:
    return TaxBrackets(
        filing_status="single",
        state="",
        federal_marginal_rate=Decimal("0.37"),
        state_marginal_rate=state,
        ltcg_rate=Decimal("0.20"),
        qualified_div_rate=Decimal("0.20"),
        niit_enabled=niit,
    )


class _StubRepo:
    def __init__(self, *, st=Decimal("0"), lt=Decimal("0"), s1256=Decimal("0"), disallowed=Decimal("0")):
        self._st = st
        self._lt = lt
        self._s1256 = s1256
        self._disallowed = disallowed

    def realized_pnl_split(self, period, account):
        return {"short_term": self._st, "long_term": self._lt}

    def section_1256_pnl(self, period, account):
        return self._s1256

    def wash_sale_disallowed_total(self, period, account):
        return self._disallowed


def _ytd():
    return Period.ytd(2026)


def test_all_short_term_gain():
    repo = _StubRepo(st=Decimal("10000"))
    r = compute_after_tax(repo, _ytd(), None, _brackets())
    assert r.estimated_tax_bill == Decimal("4080")  # 10000*0.37 + 10000*0.038
    assert r.after_tax_realized_pnl == Decimal("5920")
    assert r.tax_drag_dollar == Decimal("4080")


def test_all_long_term_gain():
    repo = _StubRepo(lt=Decimal("10000"))
    r = compute_after_tax(repo, _ytd(), None, _brackets())
    assert r.estimated_tax_bill == Decimal("2380")  # 10000*0.20 + 10000*0.038


def test_all_loss_no_negative_tax():
    repo = _StubRepo(st=Decimal("-5000"))
    r = compute_after_tax(repo, _ytd(), None, _brackets())
    assert r.estimated_tax_bill == Decimal("0")
    assert r.after_tax_realized_pnl == Decimal("-5000")
    assert r.tax_drag_dollar == Decimal("0")


def test_section_1256_60_40_split_absorbed_into_st_lt():
    repo = _StubRepo(s1256=Decimal("1000"))
    r = compute_after_tax(repo, _ytd(), None, _brackets())
    # st_tax = 400 * 0.37 = 148; lt_tax = 600 * 0.20 = 120; niit = 1000 * 0.038 = 38
    assert r.estimated_tax_bill == Decimal("306")
    assert r.section_1256_lt_portion == Decimal("600")
    assert r.section_1256_st_portion == Decimal("400")


def test_niit_toggle_off_zeroes_niit():
    repo = _StubRepo(st=Decimal("10000"))
    r = compute_after_tax(repo, _ytd(), None, _brackets(niit=False))
    assert r.estimated_tax_bill == Decimal("3700")


def test_state_tax_layer():
    repo = _StubRepo(st=Decimal("10000"))
    r = compute_after_tax(repo, _ytd(), None, _brackets(state=Decimal("0.05")))
    assert r.estimated_tax_bill == Decimal("4580")  # 3700+500+380


def test_wash_sale_marginal_cost():
    repo = _StubRepo(st=Decimal("0"), disallowed=Decimal("1000"))
    r = compute_after_tax(repo, _ytd(), None, _brackets())
    assert r.wash_sale_disallowed_total == Decimal("1000")
    assert r.wash_sale_marginal_cost == Decimal("370")


def test_effective_tax_rate():
    repo = _StubRepo(st=Decimal("10000"))
    r = compute_after_tax(repo, _ytd(), None, _brackets())
    assert r.effective_tax_rate == Decimal("0.408")


def test_effective_tax_rate_zero_when_no_gains():
    repo = _StubRepo(st=Decimal("-5000"))
    r = compute_after_tax(repo, _ytd(), None, _brackets())
    assert r.effective_tax_rate == Decimal("0")


def test_period_label_set():
    repo = _StubRepo(st=Decimal("100"))
    r = compute_after_tax(repo, _ytd(), None, _brackets())
    assert "2026" in r.period_label or "YTD" in r.period_label


def test_caveats_includes_lifetime_warning_when_lifetime():
    repo = _StubRepo(st=Decimal("100"))
    r = compute_after_tax(repo, Period.lifetime(), None, _brackets())
    assert any("Lifetime" in c or "current rates" in c for c in r.caveats)


def test_caveats_includes_capital_loss_limitation_note():
    repo = _StubRepo(st=Decimal("-100"))
    r = compute_after_tax(repo, _ytd(), None, _brackets())
    assert any("$3" in c or "capital loss" in c.lower() for c in r.caveats)


def test_realized_pnl_split_excludes_1256_at_repo_level(tmp_path):
    """Regression: §1256 contracts must be excluded from realized_pnl_split
    so they're not double-counted alongside section_1256_pnl."""
    engine = create_engine(f"sqlite:///{tmp_path}/repo.db")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        migrate(session)
        # Plant a single §1256 row (SPX option) and a single regular row (TSLA stock).
        # Need an account + import record first.
        acct = AccountRow(broker="schwab", label="personal")
        session.add(acct)
        session.commit()
        session.refresh(acct)
        imp = ImportRecordRow(
            account_id=acct.id,
            csv_filename="x.csv",
            csv_sha256="abc123",
            imported_at=datetime(2026, 1, 1, 0, 0, 0),
            trade_count=2,
        )
        session.add(imp)
        session.commit()
        session.refresh(imp)
        # SPX option (§1256 contract) — should be excluded
        session.add(
            RealizedGLLotRow(
                import_id=imp.id,
                account_id=acct.id,
                symbol_raw="SPX 4500C",
                ticker="SPX",
                closed_date="2024-09-15",
                opened_date="2024-08-15",
                quantity=1.0,
                proceeds=100.0,
                cost_basis=200.0,
                unadjusted_cost_basis=200.0,
                wash_sale=False,
                disallowed_loss=0.0,
                term="Short Term",
                option_strike=4500.0,
                option_expiry="2025-12-19",
                natural_key="spx_4500c_20240915",
            )
        )
        # TSLA stock (regular equity) — should be included
        session.add(
            RealizedGLLotRow(
                import_id=imp.id,
                account_id=acct.id,
                symbol_raw="TSLA",
                ticker="TSLA",
                closed_date="2024-09-15",
                opened_date="2024-08-15",
                quantity=10.0,
                proceeds=1000.0,
                cost_basis=2000.0,
                unadjusted_cost_basis=2000.0,
                wash_sale=False,
                disallowed_loss=0.0,
                term="Short Term",
                natural_key="tsla_20240915",
            )
        )
        session.commit()

    repo = Repository(engine)
    pnl = repo.realized_pnl_split(Period.ytd(2024), None)
    # Only TSLA should be counted (-1000); SPX excluded.
    assert pnl["short_term"] == Decimal("-1000")
    assert pnl["long_term"] == Decimal("0")
