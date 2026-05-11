from datetime import date
from decimal import Decimal

import pytest
from sqlmodel import Session, SQLModel, create_engine

import net_alpha.db.tables  # noqa: F401 — register SQLModel metadata
from net_alpha.db.migrations import migrate
from net_alpha.db.repository import Repository
from net_alpha.models.domain import Section1256MTM
from net_alpha.portfolio.after_tax import Period


@pytest.fixture()
def repo(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        migrate(session)
    return Repository(engine)


def _row(year=2025, key="SPX|4000.0|2026-06-19|C|x", account="x"):
    return Section1256MTM(
        position_key=key,
        tax_year=year,
        last_business_day=date(year, 12, 31),
        fmv=Decimal("150"),
        basis_before=Decimal("100"),
        unrealized_pnl=Decimal("50.00"),
        long_term_portion=Decimal("30.00"),
        short_term_portion=Decimal("20.00"),
        fmv_source="yahoo_close",
        ticker="SPX",
        account=account,
    )


def test_save_and_read_back_round_trip(repo):
    repo.save_section_1256_mtm([_row()])
    rows = repo.section_1256_mtm_rows(Period.for_year(2025), account=None)
    assert len(rows) == 1
    assert rows[0].fmv == Decimal("150")
    assert rows[0].unrealized_pnl == Decimal("50.00")
    assert rows[0].last_business_day == date(2025, 12, 31)


def test_save_is_idempotent_on_repeat(repo):
    repo.save_section_1256_mtm([_row()])
    repo.save_section_1256_mtm([_row()])  # second call must not duplicate
    rows = repo.section_1256_mtm_rows(Period.for_year(2025), account=None)
    assert len(rows) == 1


def test_clear_removes_all(repo):
    repo.save_section_1256_mtm([_row()])
    repo.clear_section_1256_mtm()
    rows = repo.section_1256_mtm_rows(Period.for_year(2025), account=None)
    assert rows == []


def test_pnl_sums_unrealized_within_period(repo):
    repo.save_section_1256_mtm(
        [
            _row(year=2024, key="K1"),
            _row(year=2025, key="K2"),
        ]
    )
    pnl_2025 = repo.section_1256_mtm_pnl(Period.for_year(2025), account=None)
    assert pnl_2025 == Decimal("50.00")
    pnl_life = repo.section_1256_mtm_pnl(Period.lifetime(), account=None)
    assert pnl_life == Decimal("100.00")


def test_prior_year_mtm_basis_returns_fmv(repo):
    r = _row(year=2024, key="K1")
    repo.save_section_1256_mtm([r])
    assert repo.prior_year_mtm_basis_for_position("K1", 2024) == Decimal("150")
    assert repo.prior_year_mtm_basis_for_position("K1", 2023) is None


def test_account_filter(repo):
    a = _row(year=2025, key="K1", account="x")
    b = _row(year=2025, key="K2", account="y")
    repo.save_section_1256_mtm([a, b])
    rows_x = repo.section_1256_mtm_rows(Period.for_year(2025), account="x")
    rows_y = repo.section_1256_mtm_rows(Period.for_year(2025), account="y")
    assert len(rows_x) == 1 and rows_x[0].position_key == "K1"
    assert len(rows_y) == 1 and rows_y[0].position_key == "K2"
