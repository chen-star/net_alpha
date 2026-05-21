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
ORDINARY_LOSS_CAP_MFS = Decimal("1500")


def ordinary_loss_cap(filing_status: str | None) -> Decimal:
    """§1211(b): $3,000 against ordinary income, halved to $1,500 for MFS.

    `filing_status` matches `TaxBrackets.filing_status`: single | mfj | mfs | hoh.
    None or any non-MFS value returns the standard $3,000 cap.
    """
    if filing_status is not None and filing_status.lower() == "mfs":
        return ORDINARY_LOSS_CAP_MFS
    return ORDINARY_LOSS_CAP


@dataclass(frozen=True)
class Carryforward:
    st: Decimal
    lt: Decimal
    source: Literal["user", "derived", "none"]


class _CarryforwardRepo(Protocol):
    def realized_pnl_split_by_year(self, year: int) -> tuple[Decimal, Decimal]: ...
    def earliest_trade_year(self) -> int | None: ...


class _EffectiveCarryforwardRepo(_CarryforwardRepo, Protocol):
    def get_carryforward_override(self, year: int): ...


def derive_carryforward(
    repo: _CarryforwardRepo,
    year: int,
    *,
    filing_status: str | None = None,
) -> Carryforward:
    """Replay all years from the earliest realized year up through year-1.

    Returns the (st, lt) magnitude that rolls INTO `year`. `filing_status`
    controls the §1211(b) cap (MFS halves to $1,500); when unknown, the
    standard $3,000 cap is used.
    """
    first = repo.earliest_trade_year()
    if first is None or first >= year:
        return Carryforward(st=Decimal("0"), lt=Decimal("0"), source="none")

    cap = ordinary_loss_cap(filing_status)
    st_carry = Decimal("0")
    lt_carry = Decimal("0")
    for y in range(first, year):
        st_pnl, lt_pnl = repo.realized_pnl_split_by_year(y)
        st_carry, lt_carry = _roll_one_year(st_carry, lt_carry, st_pnl, lt_pnl, cap=cap)
    return Carryforward(st=st_carry, lt=lt_carry, source="derived")


def apply_net_and_cap(
    st_in: Decimal,
    lt_in: Decimal,
    st_pnl: Decimal,
    lt_pnl: Decimal,
    *,
    cap: Decimal = ORDINARY_LOSS_CAP,
) -> tuple[Decimal, Decimal, Decimal]:
    """Apply §1212(b) bucket netting and the §1211(b) ordinary-income cap.

    Returns ``(st_carry_out, lt_carry_out, cap_used)`` — both carries are
    non-negative magnitudes; ``cap_used`` is the amount absorbed against
    ordinary income (0 ≤ cap_used ≤ cap).

    Per §1212(b)(1)(A), prior carry enters its bucket as a loss; per
    §1212(b)(1)(B), cross-bucket netting absorbs a same-year gain in the
    opposite bucket. The §1211(b) cap consumes ST loss first per Schedule D
    Capital Loss Carryover Worksheet (line 7 = line 4 + line 6; line 8 ST CF
    = line 5 − line 7); any cap remaining absorbs LT loss.
    """
    st_total = st_pnl - st_in
    lt_total = lt_pnl - lt_in

    if st_total < 0 < lt_total:
        absorbed = min(-st_total, lt_total)
        st_total += absorbed
        lt_total -= absorbed
    elif lt_total < 0 < st_total:
        absorbed = min(-lt_total, st_total)
        lt_total += absorbed
        st_total -= absorbed

    st_loss = max(Decimal("0"), -st_total)
    lt_loss = max(Decimal("0"), -lt_total)
    if st_loss == 0 and lt_loss == 0:
        return Decimal("0"), Decimal("0"), Decimal("0")

    cap_consumed_st = min(st_loss, cap)
    cap_remaining = cap - cap_consumed_st
    cap_consumed_lt = min(lt_loss, cap_remaining)
    return st_loss - cap_consumed_st, lt_loss - cap_consumed_lt, cap_consumed_st + cap_consumed_lt


def _roll_one_year(
    st_in: Decimal,
    lt_in: Decimal,
    st_pnl: Decimal,
    lt_pnl: Decimal,
    *,
    cap: Decimal = ORDINARY_LOSS_CAP,
) -> tuple[Decimal, Decimal]:
    """One-year roll honoring §1212(b) netting and §1211 $3K cap.

    Inputs:
        st_in, lt_in: prior carryforward magnitudes (positive numbers).
        st_pnl, lt_pnl: this year's signed realized P&L.

    Returns the (st, lt) carryforward magnitudes rolling INTO next year.
    See ``apply_net_and_cap`` for the full breakdown including ``cap_used``.
    """
    st_carry, lt_carry, _ = apply_net_and_cap(st_in, lt_in, st_pnl, lt_pnl, cap=cap)
    return st_carry, lt_carry


def get_effective_carryforward(
    repo: _EffectiveCarryforwardRepo,
    year: int,
    *,
    filing_status: str | None = None,
) -> Carryforward:
    """Override-wins resolution. Falls back to ``derive_carryforward``.

    A user-recorded override always wins — even when both ST and LT amounts
    are zero, an explicit zero means "I have no carryforward" and overrides
    any derived value. `filing_status` is forwarded to the derive path for
    the §1211(b) cap (MFS = $1,500; default $3,000).
    """
    override = repo.get_carryforward_override(year)
    if override is not None:
        return Carryforward(
            st=Decimal(str(override.st_amount)),
            lt=Decimal(str(override.lt_amount)),
            source="user",
        )
    return derive_carryforward(repo, year, filing_status=filing_status)
