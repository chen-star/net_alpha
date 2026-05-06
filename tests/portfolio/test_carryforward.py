from decimal import Decimal

from net_alpha.portfolio.carryforward import (
    Carryforward,
    derive_carryforward,
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
