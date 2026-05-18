"""QA-audit regression tests for §1256 bugs.

Covers:
  * H2 — `open_section_1256_positions` walked lots without FIFO-consuming
         prior sells, so a buy → sell → buy sequence produced a position
         whose basis was read from the already-disposed lot.
  * H3 — `classify_closed_trades` had the same problem at sell-time: each
         sell independently re-walked all lots from oldest, ignoring prior
         consumption.
  * H4 — `prior_year_mtm_basis_fn` returns per-contract FMV; substituting
         it directly into `basis_before` (and classifier `basis`) ignored
         quantity, producing wrong MTM/realized for any qty != 1 and an
         outright sign error for shorts carried across a year boundary.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from net_alpha.models.domain import Lot, OptionDetails, Trade
from net_alpha.section_1256.classifier import classify_closed_trades
from net_alpha.section_1256.mtm import mark_to_market, open_section_1256_positions

SPX = "SPX"
UNIVERSE = {"SPX"}


def _opt(strike: float, expiry: date, cp: str) -> OptionDetails:
    return OptionDetails(strike=strike, expiry=expiry, call_put=cp)


def _trade(action: str, qty: int, when: date, *, opt: OptionDetails, basis: float | None, proceeds: float | None,
           tid: str) -> Trade:
    return Trade(
        id=tid,
        account="x",
        date=when,
        ticker=SPX,
        action=action,
        quantity=qty,
        proceeds=proceeds,
        cost_basis=basis,
        option_details=opt,
        is_section_1256=True,
    )


def _lot(qty: int, when: date, basis: float, opt: OptionDetails, lot_id: str = "L") -> Lot:
    return Lot(
        id=lot_id,
        trade_id=lot_id,
        account="x",
        date=when,
        ticker=SPX,
        quantity=qty,
        adjusted_basis=basis,
        option_details=opt,
        cost_basis=basis,
    )


def test_open_position_basis_reads_from_still_open_lot_not_disposed_one():
    """Buy 100 @ $1/contract → Sell 100 → Buy 50 @ $5/contract sequence.

    net_qty = 50, but the still-open contracts are the SECOND buy at $5 each.
    Before the fix, basis was pulled from the first (already-disposed) lot
    yielding $50; correct answer is $250.
    """
    opt = _opt(4000.0, date(2026, 6, 19), "C")
    buy1 = _trade("Buy", 100, date(2025, 1, 1), opt=opt, basis=100.0, proceeds=None, tid="T1")
    sell1 = _trade("Sell", 100, date(2025, 4, 1), opt=opt, basis=None, proceeds=200.0, tid="T2")
    buy2 = _trade("Buy", 50, date(2025, 7, 1), opt=opt, basis=250.0, proceeds=None, tid="T3")

    lots = [_lot(100, date(2025, 1, 1), 100.0, opt, "L1"), _lot(50, date(2025, 7, 1), 250.0, opt, "L2")]
    positions = open_section_1256_positions([buy1, sell1, buy2], lots, UNIVERSE, as_of=date(2025, 12, 31))

    assert len(positions) == 1
    pos = positions[0]
    assert pos.quantity == Decimal("50")
    # basis must reflect the still-open second buy: 50 contracts × $5 = $250.
    assert pos.basis == Decimal("250")


def test_classifier_sequential_sells_track_fifo_consumption():
    """Buy 100 @ $1 → Sell 100 (gain) → Buy 50 @ $5 → Sell 50.

    Second sell's basis should come from the second buy ($250), not from the
    already-consumed first buy ($50). Before the fix, every sell re-walked
    lots independently and the second sell silently re-read the first lot.
    """
    opt = _opt(4000.0, date(2026, 6, 19), "C")
    buy1 = _trade("Buy", 100, date(2025, 1, 1), opt=opt, basis=100.0, proceeds=None, tid="T1")
    sell1 = _trade("Sell", 100, date(2025, 4, 1), opt=opt, basis=None, proceeds=200.0, tid="T2")
    buy2 = _trade("Buy", 50, date(2025, 7, 1), opt=opt, basis=250.0, proceeds=None, tid="T3")
    sell2 = _trade("Sell", 50, date(2025, 10, 1), opt=opt, basis=None, proceeds=300.0, tid="T4")

    lots = [_lot(100, date(2025, 1, 1), 100.0, opt, "L1"), _lot(50, date(2025, 7, 1), 250.0, opt, "L2")]
    classifications = classify_closed_trades([buy1, sell1, buy2, sell2], lots)

    by_trade = {c.trade_id: c for c in classifications}
    # sell1 closed the first lot: realized = 200 - 100 = 100.
    assert by_trade["T2"].realized_pnl == Decimal("100")
    # sell2 must read basis from the SECOND lot: realized = 300 - 250 = 50,
    # not 300 - 50 = 250 (which is what the old code returned).
    assert by_trade["T4"].realized_pnl == Decimal("50")


def test_prior_year_mtm_basis_scales_with_quantity_for_long():
    """For a 5-contract long carried across year-end, the prior FMV must scale
    by quantity. The bug substituted bare per-contract FMV as `basis_before`,
    producing `unrealized = 5*F2 - F1` instead of `5*(F2 - F1)`.
    """
    opt = _opt(4000.0, date(2027, 6, 18), "C")
    buy = _trade("Buy", 5, date(2024, 6, 1), opt=opt, basis=500.0, proceeds=None, tid="T1")
    lot = _lot(5, date(2024, 6, 1), 500.0, opt, "L1")

    # Year 1 (2025) FMV = $120/contract, year 2 (2026) FMV = $120/contract.
    # With FMV unchanged year-over-year, the year-2 unrealized must be zero.
    def fmv_fn(_ticker, _opt, year):
        return Decimal("120"), "yahoo_close"

    def prior_fn(_pkey, year):
        # Prior year stored FMV (per-contract) = $120.
        if year == 2025:
            return Decimal("120")
        return None

    out_2026 = mark_to_market(
        trades=[buy],
        lots=[lot],
        universe=UNIVERSE,
        tax_year=2026,
        fmv_fn=fmv_fn,
        prior_year_mtm_basis_fn=prior_fn,
    )
    assert len(out_2026) == 1
    row = out_2026[0]
    # 5 contracts × $120 - 5 × $120 = 0 (NOT 5×120 - 120 = 480).
    assert row.unrealized_pnl == Decimal("0.00")


def test_prior_year_mtm_basis_scales_with_quantity_for_short():
    """Same fix on the short branch — multi-contract short carried across
    year-end must give correct sign and magnitude. With FMV unchanged, the
    year-2 unrealized must be zero; the old code returned a very negative
    number for any qty > 1.
    """
    opt = _opt(4000.0, date(2027, 6, 18), "P")
    # Sold 3 puts for $300/contract premium ($900 total credit).
    sto = _trade(
        "Sell",
        3,
        date(2024, 6, 1),
        opt=opt,
        basis=None,
        proceeds=900.0,
        tid="T1",
    )

    def fmv_fn(_ticker, _opt, year):
        return Decimal("150"), "yahoo_close"

    def prior_fn(_pkey, year):
        if year == 2025:
            return Decimal("150")
        return None

    out_2026 = mark_to_market(
        trades=[sto],
        lots=[],  # short has no lot
        universe=UNIVERSE,
        tax_year=2026,
        fmv_fn=fmv_fn,
        prior_year_mtm_basis_fn=prior_fn,
    )
    assert len(out_2026) == 1
    # 3 contracts short, prior FMV $150 = obligation $450 (signed neg basis).
    # Year-2 FMV $150 → obligation unchanged → unrealized = $0.
    assert out_2026[0].unrealized_pnl == Decimal("0.00")
