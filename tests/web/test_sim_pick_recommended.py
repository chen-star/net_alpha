"""Unit tests for _pick_recommended in sim route.

Recommendation contract:
  - Avoid wash-sale risk first (False < True).
  - For gain sales (max pre_tax_pnl > 0): pick the strategy with highest
    after-tax P&L — keeps the most money.
  - For loss sales (all pre_tax_pnl ≤ 0): pick the strategy with most-negative
    after-tax P&L — harvests the biggest loss for offset.

Bug regression: the original implementation always picked highest after-tax,
which for a loss sale meant the SMALLEST loss — directly contradicting the
traffic-light "Lot method recommended: HIFO" hint shown on the same page
(HIFO maximizes the harvested loss).
"""

from __future__ import annotations

from decimal import Decimal

from net_alpha.engine.lot_selector import LotPickResult
from net_alpha.web.routes.sim import _pick_recommended


def _result(strategy, pre_tax, after_tax, has_wash=False):
    return LotPickResult(
        strategy=strategy,
        picks=[],
        pre_tax_pnl=Decimal(str(pre_tax)),
        st_pnl=Decimal("0"),
        lt_pnl=Decimal("0"),
        wash_sale_disallowed=Decimal("0"),
        after_tax_pnl=Decimal(str(after_tax)),
        has_wash_sale_risk=has_wash,
    )


def test_gain_sale_picks_highest_after_tax():
    """All strategies show gains → highest after-tax wins."""
    results = [
        _result("FIFO", pre_tax=500, after_tax=320),
        _result("LIFO", pre_tax=800, after_tax=510),
        _result("HIFO", pre_tax=300, after_tax=190),
    ]
    assert _pick_recommended(results) == 1  # LIFO


def test_loss_sale_picks_most_negative_after_tax_for_harvest():
    """Pure loss sale → pick the strategy that harvests the LARGEST loss
    (most-negative after-tax P&L). Matches the traffic-light HIFO hint."""
    results = [
        _result("FIFO", pre_tax=-525, after_tax=-341),  # smallest loss
        _result("LIFO", pre_tax=-37, after_tax=-24),  # tiny loss
        _result("HIFO", pre_tax=-3795, after_tax=-2745),  # biggest loss
        _result("MIN_TAX", pre_tax=-3795, after_tax=-2745),
        _result("MAX_LOSS", pre_tax=-3795, after_tax=-2745),
    ]
    # Most negative after-tax is HIFO (or MIN_TAX/MAX_LOSS tied) — input order
    # tiebreak picks the earliest (HIFO at idx 2).
    assert _pick_recommended(results) == 2


def test_mixed_pnl_picks_highest_after_tax():
    """When some strategies are gains and others are losses, treat as a gain
    decision — picking the smallest loss would penalize harvesting; picking
    the largest gain matches the user's intent (they ran the sim, they get
    to see the best realized outcome)."""
    results = [
        _result("FIFO", pre_tax=-100, after_tax=-65),
        _result("LIFO", pre_tax=200, after_tax=128),  # actual gain
        _result("HIFO", pre_tax=-500, after_tax=-325),
    ]
    assert _pick_recommended(results) == 1  # LIFO (the gain)


def test_wash_sale_strategies_deprioritized_even_when_optimal():
    """A wash-sale-tainted pick is deprioritized regardless of P&L sign.
    Wash-sale = deferred loss with basis rollover, not a clean harvest."""
    results = [
        _result("FIFO", pre_tax=-3000, after_tax=-2000, has_wash=True),  # biggest loss but tainted
        _result("LIFO", pre_tax=-100, after_tax=-65),  # tiny loss, clean
    ]
    # Clean LIFO wins over tainted FIFO even though FIFO has bigger loss.
    assert _pick_recommended(results) == 1


def test_all_zero_pnl_falls_to_input_order():
    """Edge: all strategies show zero P&L (rare but possible on flat trades)
    — input order tiebreak picks idx 0."""
    results = [
        _result("FIFO", pre_tax=0, after_tax=0),
        _result("LIFO", pre_tax=0, after_tax=0),
    ]
    assert _pick_recommended(results) == 0
