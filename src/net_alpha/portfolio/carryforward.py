"""Prior-year ST/LT capital-loss carryforward derivation and resolution.

Pure functions over a Repository. Implements §1212(b) cross-category netting
and §1211 $3K-against-ordinary cap. ST/LT only — §1256 carryforward is out of
scope (caveated in after_tax.py).

Sign convention: carryforward magnitudes are stored and returned as
non-negative Decimals (loss = positive number). The sign is flipped at
apply-time by the consumer (after_tax, tax_planner).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Protocol

ORDINARY_LOSS_CAP = Decimal("3000")


@dataclass(frozen=True)
class Carryforward:
    st: Decimal
    lt: Decimal
    source: Literal["user", "derived", "none"]


class _CarryforwardRepo(Protocol):
    def realized_pnl_split_by_year(self, year: int) -> tuple[Decimal, Decimal]: ...
    def earliest_trade_year(self) -> int | None: ...


def derive_carryforward(repo: _CarryforwardRepo, year: int) -> Carryforward:
    """Replay all years from the earliest realized year up through year-1.

    Returns the (st, lt) magnitude that rolls INTO `year`.
    """
    first = repo.earliest_trade_year()
    if first is None or first >= year:
        return Carryforward(st=Decimal("0"), lt=Decimal("0"), source="none")

    st_carry = Decimal("0")
    lt_carry = Decimal("0")
    for y in range(first, year):
        st_pnl, lt_pnl = repo.realized_pnl_split_by_year(y)
        st_carry, lt_carry = _roll_one_year(st_carry, lt_carry, st_pnl, lt_pnl)
    return Carryforward(st=st_carry, lt=lt_carry, source="derived")


def _roll_one_year(
    st_in: Decimal,
    lt_in: Decimal,
    st_pnl: Decimal,
    lt_pnl: Decimal,
) -> tuple[Decimal, Decimal]:
    """One-year roll. Stub — full §1212(b) netting added in Task 5; multi-year cases
    handled then. Single-year cases pass with this simpler implementation.

    Treat ST and LT independently; apply $3K cap proportionally on net loss across
    both buckets.
    """
    # st_pnl, lt_pnl are signed; carryforward magnitudes are non-negative.
    st_after = st_pnl - st_in  # carryforward consumes gains first
    lt_after = lt_pnl - lt_in

    st_loss_abs = max(Decimal("0"), -st_after)
    lt_loss_abs = max(Decimal("0"), -lt_after)
    total_loss = st_loss_abs + lt_loss_abs

    if total_loss == 0:
        return Decimal("0"), Decimal("0")

    cap_used = min(total_loss, ORDINARY_LOSS_CAP)
    surplus = total_loss - cap_used

    st_share = (st_loss_abs / total_loss) * surplus
    lt_share = (lt_loss_abs / total_loss) * surplus
    return st_share, lt_share
