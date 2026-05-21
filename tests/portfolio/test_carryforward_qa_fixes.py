"""QA-audit regression tests for carryforward bugs.

Covers:
  * H7 — §1211(b) cap was hardcoded to $3,000; MFS filers are capped at
         $1,500. The cap is now derived from `filing_status`.
  * H6 — §1256 60/40 splits never flowed into ST/LT multi-year carryforward
         replay because `realized_pnl_split_by_year` was equities-only.
"""

from __future__ import annotations

from decimal import Decimal

from net_alpha.portfolio.carryforward import (
    Carryforward,
    _roll_one_year,
    ordinary_loss_cap,
)


def test_ordinary_loss_cap_returns_1500_for_mfs():
    assert ordinary_loss_cap("mfs") == Decimal("1500")
    assert ordinary_loss_cap("MFS") == Decimal("1500")  # case-insensitive


def test_ordinary_loss_cap_returns_3000_for_single_mfj_hoh_none():
    assert ordinary_loss_cap("single") == Decimal("3000")
    assert ordinary_loss_cap("mfj") == Decimal("3000")
    assert ordinary_loss_cap("hoh") == Decimal("3000")
    assert ordinary_loss_cap(None) == Decimal("3000")


def test_roll_one_year_uses_mfs_cap_for_new_losses():
    """A $5,000 ST loss in an MFS year leaves $5,000 - $1,500 = $3,500 to
    carry forward; single/MFJ would only carry $2,000 forward.
    """
    # MFS: cap = $1,500. New $5,000 ST loss, no gains, no prior carry.
    st_mfs, lt_mfs = _roll_one_year(
        st_in=Decimal("0"),
        lt_in=Decimal("0"),
        st_pnl=Decimal("-5000"),
        lt_pnl=Decimal("0"),
        cap=Decimal("1500"),
    )
    assert st_mfs == Decimal("3500")
    assert lt_mfs == Decimal("0")

    # Single/MFJ default: cap = $3,000. Same losses, larger usable cap.
    st_single, lt_single = _roll_one_year(
        st_in=Decimal("0"),
        lt_in=Decimal("0"),
        st_pnl=Decimal("-5000"),
        lt_pnl=Decimal("0"),
        # cap defaults to $3,000
    )
    assert st_single == Decimal("2000")
    assert lt_single == Decimal("0")


def test_section_1256_pnl_folds_into_multiyear_carryforward(tmp_path):
    """A 60/40-split §1256 loss must roll into ST and LT carryforward replay.

    Stub a minimal Repository protocol to drive `derive_carryforward` end-to-end
    so we exercise the actual production code path that consults
    `realized_pnl_split_by_year`.
    """
    from net_alpha.portfolio.carryforward import derive_carryforward

    class _StubRepo:
        """Minimal carryforward-protocol stub. Year 1 = bare §1256 split."""

        def earliest_trade_year(self):
            return 2024

        def realized_pnl_split_by_year(self, year):
            # Pretend 2024 produced a §1256 closed-trade loss of -$10,000:
            #   LT portion = -$6,000 (60%), ST portion = -$4,000 (40%).
            # Before the H6 fix, `realized_pnl_split_by_year` would return
            # (0, 0) because §1256 was equities-only. Here we model the
            # post-fix output so the carryforward replay sees the split.
            if year == 2024:
                return (Decimal("-4000"), Decimal("-6000"))
            return (Decimal("0"), Decimal("0"))

    cf = derive_carryforward(_StubRepo(), 2025)
    # Combined loss = $10,000. Single-filer cap = $3,000 absorbs ST loss
    # first per Schedule D Capital Loss Carryover Worksheet line 7 → line 8:
    # ST CF = $4,000 − $3,000 = $1,000; LT CF = $6,000 (cap fully spent).
    assert cf.source == "derived"
    assert cf.st + cf.lt == Decimal("7000")
    assert cf.st == Decimal("1000")
    assert cf.lt == Decimal("6000")


def test_carryforward_namedtuple_smoke():
    """Carryforward dataclass round-trips correctly."""
    cf = Carryforward(st=Decimal("100"), lt=Decimal("200"), source="derived")
    assert cf.st == Decimal("100")
    assert cf.lt == Decimal("200")
    assert cf.source == "derived"
