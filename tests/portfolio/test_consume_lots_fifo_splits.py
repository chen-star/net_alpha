"""consume_lots_fifo must split-adjust pre-split sells against split-adjusted lots.

Reproduces the SQQQ bug: a 1-for-5 reverse split on 2025-11-20 rewrites the
buy lot from 100 → 20 shares (via splits/apply.py), but trade-side sells
made BEFORE the split still hold pre-split quantities (20+21+20=61). The
consumer summed pre-split sells against post-split lots and consumed
everything, reporting 0 shares remaining instead of the correct ~7.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from net_alpha.models.domain import Lot, Trade
from net_alpha.models.splits import Split
from net_alpha.portfolio.positions import consume_lots_fifo


def _sqqq_split() -> Split:
    """1-for-5 reverse split on 2025-11-20 — taken from yfinance / production DB."""
    return Split(
        id=1,
        symbol="SQQQ",
        split_date=date(2025, 11, 20),
        ratio=0.2,
        source="yahoo",
        fetched_at=datetime(2026, 4, 27),
    )


def _buy_lot() -> Lot:
    """Pre-split buy of 100 shares on 2025-06-26; after split lot.quantity = 20."""
    return Lot(
        trade_id="1",
        account="schwab/st",
        date=date(2025, 6, 26),
        ticker="SQQQ",
        quantity=20.0,  # already split-adjusted by splits/apply.py
        cost_basis=2014.0,
        adjusted_basis=2014.0,
    )


def _pre_split_sells() -> list[Trade]:
    return [
        Trade(
            account="schwab/st",
            date=date(2025, 8, 13),
            ticker="SQQQ",
            action="Sell",
            quantity=20.0,
            proceeds=340.0,
        ),
        Trade(
            account="schwab/st",
            date=date(2025, 9, 19),
            ticker="SQQQ",
            action="Sell",
            quantity=21.0,
            proceeds=329.28,
        ),
        Trade(
            account="schwab/st",
            date=date(2025, 9, 22),
            ticker="SQQQ",
            action="Sell",
            quantity=20.0,
            proceeds=306.0,
        ),
    ]


def test_consume_lots_fifo_split_aware_scales_pre_split_sells():
    """When `splits_by_ticker` is provided, sells dated before a split get
    their quantity scaled by the split ratio so they're comparable to the
    already-split-adjusted lot.quantity. Math: 61 raw × 0.2 = 12.2 scaled
    consumed; lot 20 − 12.2 = 7.8 remaining."""
    result = consume_lots_fifo(
        lots=[_buy_lot()],
        trades=_pre_split_sells(),
        splits_by_ticker={"SQQQ": [_sqqq_split()]},
    )
    assert len(result) == 1
    _lot, remaining_qty, _remaining_basis = result[0]
    assert remaining_qty == Decimal("7.8")


def test_consume_lots_fifo_no_split_param_keeps_legacy_behavior():
    """Backward-compat: when splits_by_ticker is None / omitted, behavior
    matches the pre-fix code — pre-split sells exhaust the lot."""
    result = consume_lots_fifo(
        lots=[_buy_lot()],
        trades=_pre_split_sells(),
    )
    assert result[0][1] == Decimal("0")


def test_consume_lots_fifo_does_not_scale_post_split_sells():
    """A sell dated AFTER the split is already in post-split units and
    must NOT be scaled. The 0.8-share post-split sell on 2025-11-21 (4
    pre-split shares × 0.2 = 0.8 post-split) is reported in the GL row
    in post-split units already."""
    post_split = Trade(
        account="schwab/st",
        date=date(2025, 11, 21),
        ticker="SQQQ",
        action="Sell",
        quantity=0.8,
        proceeds=64.35,
    )
    result = consume_lots_fifo(
        lots=[_buy_lot()],
        trades=[*_pre_split_sells(), post_split],
        splits_by_ticker={"SQQQ": [_sqqq_split()]},
    )
    # 20 - (12.2 + 0.8) = 7.0
    assert result[0][1] == Decimal("7.0")


def test_consume_lots_fifo_unknown_ticker_in_splits_map_is_noop():
    """A splits_by_ticker entry for a different ticker doesn't disturb
    other tickers."""
    other_lot = Lot(
        trade_id="2",
        account="schwab/st",
        date=date(2024, 1, 1),
        ticker="AAPL",
        quantity=10.0,
        cost_basis=1500.0,
        adjusted_basis=1500.0,
    )
    other_sell = Trade(
        account="schwab/st",
        date=date(2025, 6, 1),
        ticker="AAPL",
        action="Sell",
        quantity=3.0,
        proceeds=600.0,
    )
    result = consume_lots_fifo(
        lots=[other_lot],
        trades=[other_sell],
        splits_by_ticker={"SQQQ": [_sqqq_split()]},
    )
    assert result[0][1] == Decimal("7")  # 10 - 3, untouched
