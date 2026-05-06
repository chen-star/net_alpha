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
    """One-year roll honoring §1212(b) netting and §1211 $3K cap.

    Inputs:
        st_in, lt_in: prior carryforward magnitudes (positive numbers).
        st_pnl, lt_pnl: this year's signed realized P&L.

    Returns the (st, lt) carryforward magnitudes rolling INTO next year.

    Semantics: the prior carryforward has already had its §1211 cap applied
    in a prior year, so it is consumed by this year's gains FIRST and any
    residual rolls forward without re-capping. Only NEW losses originating
    this year are subject to the $3K cap. Cross-category netting per
    §1212(b)(1)(B) applies to both the carry-vs-gains and new-loss-vs-gains
    steps.
    """
    # 1) Split this year's P&L into per-bucket gains vs new losses.
    st_new_loss = max(Decimal("0"), -st_pnl)
    lt_new_loss = max(Decimal("0"), -lt_pnl)
    st_gain = max(Decimal("0"), st_pnl)
    lt_gain = max(Decimal("0"), lt_pnl)

    # 2) Apply prior carryforward against this year's gains, same bucket first,
    #    then cross-category per §1212(b)(1)(B). Residual carry rolls forward
    #    without re-capping.
    st_carry = st_in
    lt_carry = lt_in

    # Same-bucket absorption.
    absorbed = min(st_carry, st_gain)
    st_carry -= absorbed
    st_gain -= absorbed
    absorbed = min(lt_carry, lt_gain)
    lt_carry -= absorbed
    lt_gain -= absorbed

    # Cross-bucket absorption: ST carry vs LT gain, LT carry vs ST gain.
    absorbed = min(st_carry, lt_gain)
    st_carry -= absorbed
    lt_gain -= absorbed
    absorbed = min(lt_carry, st_gain)
    lt_carry -= absorbed
    st_gain -= absorbed

    # 3) Apply this year's new losses against any remaining gains (same
    #    bucket first, then cross-category).
    absorbed = min(st_new_loss, st_gain)
    st_new_loss -= absorbed
    st_gain -= absorbed
    absorbed = min(lt_new_loss, lt_gain)
    lt_new_loss -= absorbed
    lt_gain -= absorbed

    absorbed = min(st_new_loss, lt_gain)
    st_new_loss -= absorbed
    lt_gain -= absorbed
    absorbed = min(lt_new_loss, st_gain)
    lt_new_loss -= absorbed
    st_gain -= absorbed

    # 4) §1211 $3K cap on this year's NEW net losses only.
    new_total = st_new_loss + lt_new_loss
    if new_total > 0:
        cap_used = min(new_total, ORDINARY_LOSS_CAP)
        surplus = new_total - cap_used
        if surplus > 0:
            # Per Schedule D Capital Loss Carryover Worksheet, surplus retains
            # character proportionally. Quantize to whole cents to avoid
            # repeating-decimal artifacts from Decimal division.
            st_share = (st_new_loss / new_total * surplus).quantize(Decimal("0.01"))
            lt_share = surplus - st_share
        else:
            st_share = Decimal("0")
            lt_share = Decimal("0")
    else:
        st_share = Decimal("0")
        lt_share = Decimal("0")

    # 5) Total carry into next year = unconsumed prior carry + new surplus.
    return st_carry + st_share, lt_carry + lt_share
