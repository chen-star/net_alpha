"""Multi-account filter behaviour of Repository SQL methods (Task 7).

Covers the OR semantic for cross-account violations/exempt-matches and confirms
that ``accounts=["X"]`` is equivalent to the legacy ``account="X"`` path.

Column-type coverage:
  - TEXT account column:  ExemptMatchRow (loss_account / buy_account)
  - TEXT account column:  Section1256MTMRow (account)
  - FK int column:        WashSaleViolationRow (loss_account_id / buy_account_id)
  - FK int column:        Section1256ClassificationRow → TradeRow.account_id
  - FK int column:        RealizedGLLotRow.account_id
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
    ExemptMatchRow,
    ImportRecordRow,
    RealizedGLLotRow,
    TradeRow,
    WashSaleViolationRow,
)
from net_alpha.models.domain import Section1256MTM
from net_alpha.portfolio.after_tax import Period


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def repo(tmp_path):
    """In-memory-style repo with full schema + migrations, two accounts pre-seeded."""
    engine = create_engine(f"sqlite:///{tmp_path}/filter_test.db")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        migrate(session)
    r = Repository(engine)
    r.get_or_create_account("Schwab", "A")
    r.get_or_create_account("Schwab", "B")
    return r


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_exempt_match(repo: Repository, *, loss_acct: str, buy_acct: str, year: int = 2025) -> None:
    """Insert a minimal ExemptMatchRow.  Uses fake trade IDs — SQLite doesn't
    enforce FK constraints by default so raw insertion works fine."""
    with Session(repo.engine) as s:
        # Need real trade rows because ExemptMatchRow has FK -> trades.id.
        # Plant two minimal TradeRows first, using account IDs from the repo.
        a = repo.get_account("Schwab", "A")
        b = repo.get_account("Schwab", "B")
        acct_by_display = {"Schwab/A": a, "Schwab/B": b}

        loss_acct_obj = acct_by_display[loss_acct]
        buy_acct_obj = acct_by_display[buy_acct]

        loss_trade = TradeRow(
            account_id=loss_acct_obj.id,
            natural_key=f"loss_{loss_acct}_{year}_exempt",
            ticker="SPX",
            trade_date=f"{year}-10-01",
            action="Sell",
            quantity=1.0,
            proceeds=100.0,
            cost_basis=200.0,
            is_section_1256=True,
        )
        buy_trade = TradeRow(
            account_id=buy_acct_obj.id,
            natural_key=f"buy_{buy_acct}_{year}_exempt",
            ticker="SPX",
            trade_date=f"{year}-10-15",
            action="Buy",
            quantity=1.0,
            cost_basis=150.0,
            is_section_1256=True,
        )
        s.add(loss_trade)
        s.add(buy_trade)
        s.flush()

        s.add(
            ExemptMatchRow(
                loss_trade_id=loss_trade.id,
                triggering_buy_id=buy_trade.id,
                exempt_reason="section_1256",
                rule_citation="IRC §1256(c)",
                notional_disallowed=Decimal("100"),
                confidence="Confirmed",
                matched_quantity=1.0,
                loss_account=loss_acct,
                buy_account=buy_acct,
                loss_sale_date=f"{year}-10-01",
                triggering_buy_date=f"{year}-10-15",
                ticker="SPX",
            )
        )
        s.commit()


def _seed_wash_sale_violation(
    repo: Repository,
    *,
    loss_acct_display: str,
    buy_acct_display: str,
    disallowed: Decimal = Decimal("250"),
    year: int = 2025,
    kind: str = "deferred",
) -> None:
    """Insert a minimal WashSaleViolationRow with real account IDs."""
    broker_loss, label_loss = loss_acct_display.split("/", 1)
    broker_buy, label_buy = buy_acct_display.split("/", 1)
    loss_acct = repo.get_account(broker_loss, label_loss)
    buy_acct = repo.get_account(broker_buy, label_buy)
    assert loss_acct is not None and buy_acct is not None

    with Session(repo.engine) as s:
        loss_trade = TradeRow(
            account_id=loss_acct.id,
            natural_key=f"loss_{loss_acct_display}_{year}_{kind}",
            ticker="SPY",
            trade_date=f"{year}-03-01",
            action="Sell",
            quantity=10.0,
            proceeds=1000.0,
            cost_basis=1250.0,
        )
        buy_trade = TradeRow(
            account_id=buy_acct.id,
            natural_key=f"buy_{buy_acct_display}_{year}_{kind}",
            ticker="SPY",
            trade_date=f"{year}-03-15",
            action="Buy",
            quantity=10.0,
            cost_basis=1100.0,
        )
        s.add(loss_trade)
        s.add(buy_trade)
        s.flush()

        s.add(
            WashSaleViolationRow(
                loss_trade_id=loss_trade.id,
                replacement_trade_id=buy_trade.id,
                loss_account_id=loss_acct.id,
                buy_account_id=buy_acct.id,
                ticker="SPY",
                loss_sale_date=f"{year}-03-01",
                triggering_buy_date=f"{year}-03-15",
                confidence="Confirmed",
                disallowed_loss=float(disallowed),
                matched_quantity=10.0,
                kind=kind,
            )
        )
        s.commit()


# ---------------------------------------------------------------------------
# list_exempt_matches
# ---------------------------------------------------------------------------


def test_exempt_matches_accounts_list_single_matches_legacy(repo):
    """accounts=['Schwab/A'] must return the same rows as account='Schwab/A'."""
    _seed_exempt_match(repo, loss_acct="Schwab/A", buy_acct="Schwab/B")

    legacy = repo.list_exempt_matches(account="Schwab/A")
    new = repo.list_exempt_matches(accounts=["Schwab/A"])

    assert len(legacy) == 1
    assert [(r.loss_account, r.buy_account) for r in legacy] == [
        (r.loss_account, r.buy_account) for r in new
    ]


def test_exempt_matches_cross_account_or_semantic(repo):
    """Cross-account exempt match (loss=A, buy=B) shows up under filter {A} AND {B}."""
    _seed_exempt_match(repo, loss_acct="Schwab/A", buy_acct="Schwab/B")

    only_a = repo.list_exempt_matches(accounts=["Schwab/A"])
    only_b = repo.list_exempt_matches(accounts=["Schwab/B"])

    assert len(only_a) == 1
    assert len(only_b) == 1


def test_exempt_matches_multi_account_union(repo):
    """accounts=['A', 'B'] returns the union (deduplicated by row identity)."""
    _seed_exempt_match(repo, loss_acct="Schwab/A", buy_acct="Schwab/B")

    both = repo.list_exempt_matches(accounts=["Schwab/A", "Schwab/B"])
    # The row matches EITHER side, but it's a single row — SQL IN de-dupes it.
    assert len(both) == 1


def test_exempt_matches_empty_accounts_returns_all(repo):
    """accounts=[] and accounts=None both mean no filter — return everything."""
    _seed_exempt_match(repo, loss_acct="Schwab/A", buy_acct="Schwab/B")

    via_empty_list = repo.list_exempt_matches(accounts=[])
    via_none = repo.list_exempt_matches(accounts=None)

    assert len(via_empty_list) == 1
    assert len(via_none) == 1


def test_exempt_matches_unrelated_account_returns_empty(repo):
    """Filter on an account that has no matches returns []."""
    _seed_exempt_match(repo, loss_acct="Schwab/A", buy_acct="Schwab/B")

    result = repo.list_exempt_matches(accounts=["Schwab/Other"])
    assert result == []


# ---------------------------------------------------------------------------
# section_1256_mtm_rows / section_1256_mtm_pnl
# ---------------------------------------------------------------------------


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


def test_mtm_rows_accounts_list_filter(repo):
    """Multi-account filter on the TEXT account column."""
    p = Period.for_year(2025)
    repo.save_section_1256_mtm([_mtm_row("Schwab/A", "ka"), _mtm_row("Schwab/B", "kb")])

    both = repo.section_1256_mtm_rows(p, account=None, accounts=["Schwab/A", "Schwab/B"])
    just_a = repo.section_1256_mtm_rows(p, account=None, accounts=["Schwab/A"])
    no_filter = repo.section_1256_mtm_rows(p, account=None, accounts=None)

    assert len(both) == 2
    assert len(just_a) == 1
    assert just_a[0].account == "Schwab/A"
    assert len(no_filter) == 2


def test_mtm_rows_accounts_list_single_matches_legacy(repo):
    """accounts=['Schwab/A'] must equal account='Schwab/A'."""
    p = Period.for_year(2025)
    repo.save_section_1256_mtm([_mtm_row("Schwab/A", "ka"), _mtm_row("Schwab/B", "kb")])

    legacy = repo.section_1256_mtm_rows(p, account="Schwab/A")
    new = repo.section_1256_mtm_rows(p, account=None, accounts=["Schwab/A"])

    assert [r.account for r in legacy] == [r.account for r in new]


def test_mtm_pnl_accounts_list_filter(repo):
    """section_1256_mtm_pnl delegates correctly to section_1256_mtm_rows."""
    p = Period.for_year(2025)
    repo.save_section_1256_mtm([_mtm_row("Schwab/A", "ka"), _mtm_row("Schwab/B", "kb")])

    total = repo.section_1256_mtm_pnl(p, account=None, accounts=["Schwab/A", "Schwab/B"])
    just_a = repo.section_1256_mtm_pnl(p, account=None, accounts=["Schwab/A"])

    assert total == Decimal("100")
    assert just_a == Decimal("50")


# ---------------------------------------------------------------------------
# wash_sale_disallowed_by_kind / wash_sale_disallowed_total
# ---------------------------------------------------------------------------


def test_wash_sale_disallowed_by_kind_or_semantic(repo):
    """Cross-account wash sale (loss=A, buy=B): both {A} and {B} filters include it."""
    _seed_wash_sale_violation(repo, loss_acct_display="Schwab/A", buy_acct_display="Schwab/B")
    p = Period.for_year(2025)

    only_a = repo.wash_sale_disallowed_by_kind(p, account=None, accounts=["Schwab/A"])
    only_b = repo.wash_sale_disallowed_by_kind(p, account=None, accounts=["Schwab/B"])
    only_other = repo.wash_sale_disallowed_by_kind(p, account=None, accounts=["Schwab/Other"])

    assert only_a["deferred"] == Decimal("250")
    assert only_b["deferred"] == Decimal("250")
    assert only_other["deferred"] == Decimal("0")


def test_wash_sale_disallowed_by_kind_accounts_single_matches_legacy(repo):
    """accounts=['Schwab/A'] must equal account='Schwab/A'."""
    _seed_wash_sale_violation(repo, loss_acct_display="Schwab/A", buy_acct_display="Schwab/A")
    p = Period.for_year(2025)

    legacy = repo.wash_sale_disallowed_by_kind(p, account="Schwab/A")
    new = repo.wash_sale_disallowed_by_kind(p, account=None, accounts=["Schwab/A"])

    assert legacy["deferred"] == new["deferred"]


def test_wash_sale_disallowed_total_or_semantic(repo):
    """wash_sale_disallowed_total delegates to by_kind and respects the accounts list."""
    _seed_wash_sale_violation(repo, loss_acct_display="Schwab/A", buy_acct_display="Schwab/B")
    p = Period.for_year(2025)

    total_a = repo.wash_sale_disallowed_total(p, account=None, accounts=["Schwab/A"])
    total_b = repo.wash_sale_disallowed_total(p, account=None, accounts=["Schwab/B"])
    total_other = repo.wash_sale_disallowed_total(p, account=None, accounts=["Schwab/Other"])

    assert total_a == Decimal("250")
    assert total_b == Decimal("250")
    assert total_other == Decimal("0")


def test_wash_sale_disallowed_by_kind_empty_accounts_no_filter(repo):
    """accounts=[] and accounts=None both mean no filter."""
    _seed_wash_sale_violation(repo, loss_acct_display="Schwab/A", buy_acct_display="Schwab/B")
    p = Period.for_year(2025)

    via_empty = repo.wash_sale_disallowed_by_kind(p, account=None, accounts=[])
    via_none = repo.wash_sale_disallowed_by_kind(p, account=None, accounts=None)

    assert via_empty["deferred"] == Decimal("250")
    assert via_none["deferred"] == Decimal("250")


# ---------------------------------------------------------------------------
# realized_pnl_split (FK int column via RealizedGLLotRow.account_id)
# ---------------------------------------------------------------------------


def _seed_realized_gl(repo: Repository, *, acct_display: str, pnl: Decimal, year: int = 2025) -> None:
    """Plant a single RealizedGLLotRow for the given account."""
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


def test_realized_pnl_split_accounts_list_filter(repo):
    """accounts=['Schwab/A'] only sums lots belonging to account A."""
    _seed_realized_gl(repo, acct_display="Schwab/A", pnl=Decimal("200"))
    _seed_realized_gl(repo, acct_display="Schwab/B", pnl=Decimal("300"))
    p = Period.for_year(2025)

    only_a = repo.realized_pnl_split(p, account=None, accounts=["Schwab/A"])
    only_b = repo.realized_pnl_split(p, account=None, accounts=["Schwab/B"])
    both = repo.realized_pnl_split(p, account=None, accounts=["Schwab/A", "Schwab/B"])
    no_filter = repo.realized_pnl_split(p, account=None, accounts=None)

    assert only_a["short_term"] == Decimal("200")
    assert only_b["short_term"] == Decimal("300")
    assert both["short_term"] == Decimal("500")
    assert no_filter["short_term"] == Decimal("500")


def test_realized_pnl_split_accounts_list_single_matches_legacy(repo):
    """accounts=['Schwab/A'] must equal account='Schwab/A'."""
    _seed_realized_gl(repo, acct_display="Schwab/A", pnl=Decimal("150"))
    p = Period.for_year(2025)

    legacy = repo.realized_pnl_split(p, account="Schwab/A")
    new = repo.realized_pnl_split(p, account=None, accounts=["Schwab/A"])

    assert legacy["short_term"] == new["short_term"]
    assert legacy["long_term"] == new["long_term"]


def test_realized_pnl_split_unknown_account_returns_zero(repo):
    """accounts=['Schwab/Unknown'] returns zeros — no crash."""
    _seed_realized_gl(repo, acct_display="Schwab/A", pnl=Decimal("100"))
    p = Period.for_year(2025)

    result = repo.realized_pnl_split(p, account=None, accounts=["Schwab/Unknown"])
    assert result == {"short_term": Decimal("0"), "long_term": Decimal("0")}


# ---------------------------------------------------------------------------
# list_section_1256_classifications (FK int via TradeRow.account_id)
# ---------------------------------------------------------------------------


def _seed_section_1256_classification(
    repo: Repository, *, acct_display: str, realized_pnl: Decimal, year: int = 2025
) -> None:
    """Seed a Section1256ClassificationRow with a real TradeRow parent."""
    from net_alpha.db.tables import Section1256ClassificationRow

    broker, label = acct_display.split("/", 1)
    acct = repo.get_account(broker, label)
    assert acct is not None

    with Session(repo.engine) as s:
        trade = TradeRow(
            account_id=acct.id,
            natural_key=f"spx_trade_{acct_display}_{year}",
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


def test_list_section_1256_classifications_accounts_list_filter(repo):
    """accounts=['Schwab/A'] only returns classifications from account A."""
    _seed_section_1256_classification(repo, acct_display="Schwab/A", realized_pnl=Decimal("1000"))
    _seed_section_1256_classification(repo, acct_display="Schwab/B", realized_pnl=Decimal("2000"))

    only_a = repo.list_section_1256_classifications(accounts=["Schwab/A"])
    only_b = repo.list_section_1256_classifications(accounts=["Schwab/B"])
    both = repo.list_section_1256_classifications(accounts=["Schwab/A", "Schwab/B"])
    no_filter = repo.list_section_1256_classifications(accounts=None)

    assert len(only_a) == 1
    assert only_a[0].realized_pnl == Decimal("1000")
    assert len(only_b) == 1
    assert only_b[0].realized_pnl == Decimal("2000")
    assert len(both) == 2
    assert len(no_filter) == 2


def test_list_section_1256_classifications_accounts_single_matches_legacy(repo):
    """accounts=['Schwab/A'] must equal account='Schwab/A'."""
    _seed_section_1256_classification(repo, acct_display="Schwab/A", realized_pnl=Decimal("500"))

    legacy = repo.list_section_1256_classifications(account="Schwab/A")
    new = repo.list_section_1256_classifications(accounts=["Schwab/A"])

    assert len(legacy) == len(new) == 1
    assert legacy[0].realized_pnl == new[0].realized_pnl


def test_list_section_1256_classifications_empty_accounts_no_filter(repo):
    """accounts=[] and accounts=None both mean no filter."""
    _seed_section_1256_classification(repo, acct_display="Schwab/A", realized_pnl=Decimal("300"))

    via_empty = repo.list_section_1256_classifications(accounts=[])
    via_none = repo.list_section_1256_classifications(accounts=None)

    assert len(via_empty) == 1
    assert len(via_none) == 1


# ---------------------------------------------------------------------------
# section_1256_pnl (FK int via TradeRow.account_id)
# ---------------------------------------------------------------------------


def test_section_1256_pnl_accounts_list_filter(repo):
    """accounts=['Schwab/A'] only sums §1256 PnL from account A."""
    _seed_section_1256_classification(repo, acct_display="Schwab/A", realized_pnl=Decimal("1000"))
    _seed_section_1256_classification(repo, acct_display="Schwab/B", realized_pnl=Decimal("2000"))
    p = Period.for_year(2025)

    only_a = repo.section_1256_pnl(p, account=None, accounts=["Schwab/A"])
    only_b = repo.section_1256_pnl(p, account=None, accounts=["Schwab/B"])
    both = repo.section_1256_pnl(p, account=None, accounts=["Schwab/A", "Schwab/B"])

    assert only_a == Decimal("1000")
    assert only_b == Decimal("2000")
    assert both == Decimal("3000")
