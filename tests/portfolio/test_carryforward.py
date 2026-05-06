from decimal import Decimal
from decimal import Decimal as D

from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

from net_alpha.db.migrations import migrate
from net_alpha.db.repository import Repository
from net_alpha.portfolio.carryforward import (
    Carryforward,
    derive_carryforward,
    get_effective_carryforward,
)


class _StubRepo:
    """Pure-function stub. Returns the (st, lt) realized P&L for each year."""

    def __init__(self, by_year: dict[int, tuple[Decimal, Decimal]]):
        self._by = by_year

    def realized_pnl_split_by_year(self, year: int) -> tuple[Decimal, Decimal]:
        return self._by.get(year, (Decimal("0"), Decimal("0")))

    def earliest_trade_year(self) -> int | None:
        return min(self._by) if self._by else None


def test_no_prior_history_returns_none_source():
    repo = _StubRepo({})
    cf = derive_carryforward(repo, year=2025)
    assert cf == Carryforward(st=Decimal("0"), lt=Decimal("0"), source="none")


def test_single_prior_year_st_loss_below_cap():
    # 2024 had a $1,500 ST loss. Below the $3,000 cap, all absorbed against
    # ordinary, nothing rolls forward.
    repo = _StubRepo({2024: (Decimal("-1500"), Decimal("0"))})
    cf = derive_carryforward(repo, year=2025)
    assert cf == Carryforward(st=Decimal("0"), lt=Decimal("0"), source="derived")


def test_single_prior_year_st_loss_above_cap_rolls_forward():
    # 2024 had a $5,000 ST loss. $3,000 absorbed against ordinary; $2,000 rolls.
    repo = _StubRepo({2024: (Decimal("-5000"), Decimal("0"))})
    cf = derive_carryforward(repo, year=2025)
    assert cf == Carryforward(st=Decimal("2000"), lt=Decimal("0"), source="derived")


def test_single_prior_year_lt_loss_above_cap_rolls_forward():
    repo = _StubRepo({2024: (Decimal("0"), Decimal("-5000"))})
    cf = derive_carryforward(repo, year=2025)
    assert cf == Carryforward(st=Decimal("0"), lt=Decimal("2000"), source="derived")


def test_single_prior_year_pure_gain_no_carryforward():
    repo = _StubRepo({2024: (Decimal("1000"), Decimal("2000"))})
    cf = derive_carryforward(repo, year=2025)
    assert cf == Carryforward(st=Decimal("0"), lt=Decimal("0"), source="derived")


def test_excess_st_loss_offsets_lt_gain_same_year():
    # 2024: ST loss $5,000, LT gain $2,000.
    # ST loss first absorbs $2,000 of LT gain → ST net $3,000 loss, LT net 0.
    # $3,000 absorbed against ordinary; nothing rolls.
    repo = _StubRepo({2024: (Decimal("-5000"), Decimal("2000"))})
    cf = derive_carryforward(repo, year=2025)
    assert cf == Carryforward(st=Decimal("0"), lt=Decimal("0"), source="derived")


def test_excess_st_loss_partially_absorbed_by_lt_gain_then_rolls():
    # 2024: ST loss $10,000, LT gain $3,000.
    # ST loss absorbs $3,000 LT gain → ST net $7,000 loss.
    # $3,000 against ordinary, $4,000 rolls forward as ST.
    repo = _StubRepo({2024: (Decimal("-10000"), Decimal("3000"))})
    cf = derive_carryforward(repo, year=2025)
    assert cf == Carryforward(st=Decimal("4000"), lt=Decimal("0"), source="derived")


def test_excess_lt_loss_offsets_st_gain():
    # 2024: ST gain $1,000, LT loss $6,000.
    # LT loss absorbs $1,000 ST gain → LT net $5,000 loss.
    # $3,000 against ordinary, $2,000 rolls forward as LT.
    repo = _StubRepo({2024: (Decimal("1000"), Decimal("-6000"))})
    cf = derive_carryforward(repo, year=2025)
    assert cf == Carryforward(st=Decimal("0"), lt=Decimal("2000"), source="derived")


def test_both_categories_negative_each_rolls_in_bucket():
    # 2024: ST loss $4,000, LT loss $2,000. Total $6,000 loss.
    # $3,000 against ordinary; $3,000 surplus splits proportionally:
    #   ST share = 4000/6000 * 3000 = 2000
    #   LT share = 2000/6000 * 3000 = 1000
    repo = _StubRepo({2024: (Decimal("-4000"), Decimal("-2000"))})
    cf = derive_carryforward(repo, year=2025)
    assert cf == Carryforward(st=Decimal("2000"), lt=Decimal("1000"), source="derived")


def test_two_year_chain_carryforward_consumes_next_year_gain():
    # 2023: ST loss $5,000 → $2,000 ST carry into 2024.
    # 2024: ST gain $1,500 → carry consumed down to $500 ST.
    # $500 carries into 2025.
    repo = _StubRepo(
        {
            2023: (Decimal("-5000"), Decimal("0")),
            2024: (Decimal("1500"), Decimal("0")),
        }
    )
    cf = derive_carryforward(repo, year=2025)
    assert cf == Carryforward(st=Decimal("500"), lt=Decimal("0"), source="derived")


def test_three_year_chain_with_cross_category():
    # 2022: ST loss $10,000 → $7,000 carry into 2023 (after $3K cap).
    # 2023: ST gain $2,000, LT gain $5,000. Carry first absorbs ST gain ($2,000 → 0),
    #       remaining $5,000 ST carry crosses to absorb LT gain ($5,000 → 0).
    #       Net for 2023: 0/0. Nothing new rolls. Carry into 2024: 0/0.
    # 2024: ST loss $1,000. $1,000 against ordinary. Nothing rolls.
    # Carry into 2025: 0/0.
    repo = _StubRepo(
        {
            2022: (Decimal("-10000"), Decimal("0")),
            2023: (Decimal("2000"), Decimal("5000")),
            2024: (Decimal("-1000"), Decimal("0")),
        }
    )
    cf = derive_carryforward(repo, year=2025)
    assert cf == Carryforward(st=Decimal("0"), lt=Decimal("0"), source="derived")


def _real_repo() -> Repository:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        migrate(session)
    return Repository(engine)


def test_user_override_beats_derived():
    repo = _real_repo()
    repo.upsert_carryforward_override(year=2025, st=D("999"), lt=D("0"))
    cf = get_effective_carryforward(repo, year=2025)
    assert cf.source == "user"
    assert cf.st == D("999")


def test_user_override_zero_still_beats_derived():
    """Explicit zero override means 'I have no carryforward' — beats derive."""
    repo = _real_repo()
    repo.upsert_carryforward_override(year=2025, st=D("0"), lt=D("0"))
    cf = get_effective_carryforward(repo, year=2025)
    assert cf.source == "user"
    assert cf == Carryforward(st=D("0"), lt=D("0"), source="user")


def test_falls_back_to_derived_when_no_override():
    repo = _real_repo()
    cf = get_effective_carryforward(repo, year=2025)
    # No trades in repo → "none"
    assert cf.source == "none"
