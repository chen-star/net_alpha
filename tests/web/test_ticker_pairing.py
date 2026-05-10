"""Tests for the trade-pairing presentation-layer transform.

Each test exercises one rule from
docs/superpowers/specs/2026-05-10-ticker-trade-pairings-design.md.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest

from net_alpha.models.domain import Lot, OptionDetails, Trade
from net_alpha.web.pairing import PairFields, compute_pair_fields


def test_module_smoke_returns_empty_dict_for_no_rows():
    result = compute_pair_fields(timeline_rows=[], lots=[], open_lot_ids=set())
    assert result == {}


@dataclass
class FakeTimelineRow:
    """Stand-in for routes.ticker.TimelineRow during pairing unit tests."""
    trade: Trade
    assigned_from: OptionDetails | None = None


def test_simple_btc_pair_assigns_open_close_roles():
    sto = Trade(
        id="t-sto", account="Schwab/main", date=date(2026, 1, 3), ticker="AAPL",
        action="Sell", quantity=1.0, proceeds=215.0, cost_basis=None,
        basis_source="option_short_open",
        option_details=OptionDetails(strike=150.0, expiry=date(2026, 2, 15), call_put="P"),
    )
    btc = Trade(
        id="t-btc", account="Schwab/main", date=date(2026, 2, 3), ticker="AAPL",
        action="Buy", quantity=1.0, proceeds=None, cost_basis=5.0,
        basis_source="option_short_close",
        option_details=OptionDetails(strike=150.0, expiry=date(2026, 2, 15), call_put="P"),
    )
    rows = [FakeTimelineRow(trade=sto), FakeTimelineRow(trade=btc)]

    fields = compute_pair_fields(timeline_rows=rows, lots=[], open_lot_ids=set())

    assert fields["t-sto"].pair_key == fields["t-btc"].pair_key
    assert fields["t-sto"].pair_key is not None
    assert fields["t-sto"].pair_role == "open"
    assert fields["t-btc"].pair_role == "close"
    assert fields["t-sto"].pair_position == (1, 1)
    assert fields["t-btc"].pair_position == (1, 1)
    assert fields["t-sto"].pair_cap == "top"
    assert fields["t-btc"].pair_cap == "bottom"
    assert fields["t-sto"].partner_trade_id == "t-btc"
    assert fields["t-btc"].partner_trade_id == "t-sto"


def test_scale_in_close_groups_three_rows_under_one_pair():
    common = dict(account="Schwab/main", ticker="AAPL", basis_source="option_short_open",
                  option_details=OptionDetails(strike=165.0, expiry=date(2026, 4, 19), call_put="C"))
    sto1 = Trade(id="t-sto1", date=date(2026, 3, 5), action="Sell", quantity=1.0, proceeds=95.0, cost_basis=None, **common)
    sto2 = Trade(id="t-sto2", date=date(2026, 3, 10), action="Sell", quantity=1.0, proceeds=110.0, cost_basis=None, **common)
    btc = Trade(
        id="t-btc", account="Schwab/main", date=date(2026, 3, 20), ticker="AAPL",
        action="Buy", quantity=2.0, proceeds=None, cost_basis=30.0,
        basis_source="option_short_close",
        option_details=OptionDetails(strike=165.0, expiry=date(2026, 4, 19), call_put="C"),
    )
    rows = [FakeTimelineRow(trade=sto1), FakeTimelineRow(trade=sto2), FakeTimelineRow(trade=btc)]

    fields = compute_pair_fields(timeline_rows=rows, lots=[], open_lot_ids=set())

    assert fields["t-sto1"].pair_key == fields["t-sto2"].pair_key == fields["t-btc"].pair_key
    assert fields["t-sto1"].pair_position == (1, 2)
    assert fields["t-sto2"].pair_position == (2, 2)
    assert fields["t-btc"].pair_position == (1, 1)
    assert fields["t-sto1"].pair_cap == "top"
    assert fields["t-sto2"].pair_cap == "none"
    assert fields["t-btc"].pair_cap == "bottom"


def test_synthetic_expiry_row_joins_parent_pair():
    sto = Trade(
        id="t-sto", account="Schwab/main", date=date(2026, 4, 1), ticker="AAPL",
        action="Sell", quantity=1.0, proceeds=45.0, cost_basis=None,
        basis_source="option_short_open",
        option_details=OptionDetails(strike=170.0, expiry=date(2026, 4, 19), call_put="C"),
    )
    # Synth row built by _build_timeline_rows: same key, basis_source = option_short_close_expiry.
    synth = Trade(
        id="t-synth", account="Schwab/main", date=date(2026, 4, 19), ticker="AAPL",
        action="Buy", quantity=1.0, proceeds=None, cost_basis=0.0,
        basis_source="option_short_close_expiry",
        option_details=OptionDetails(strike=170.0, expiry=date(2026, 4, 19), call_put="C"),
    )
    rows = [FakeTimelineRow(trade=sto), FakeTimelineRow(trade=synth)]

    fields = compute_pair_fields(timeline_rows=rows, lots=[], open_lot_ids=set())

    assert fields["t-sto"].pair_key == fields["t-synth"].pair_key
    assert fields["t-synth"].pair_role == "close"
    assert fields["t-synth"].pair_cap == "bottom"


def _lot_from_buy(trade: Trade, lot_id: str) -> Lot:
    return Lot(
        id=lot_id,
        trade_id=trade.id,
        account=trade.account,
        date=trade.date,
        ticker=trade.ticker,
        quantity=trade.quantity,
        cost_basis=trade.cost_basis or 0.0,
        adjusted_basis=trade.cost_basis or 0.0,
    )


def test_still_open_stock_lot_has_still_open_role():
    buy = Trade(id="t-buy", account="Schwab/main", date=date(2026, 1, 10),
                ticker="AAPL", action="Buy", quantity=100.0, cost_basis=14800.0)
    lot = _lot_from_buy(buy, lot_id="L-1")
    rows = [FakeTimelineRow(trade=buy)]

    fields = compute_pair_fields(timeline_rows=rows, lots=[lot], open_lot_ids={"L-1"})

    assert fields["t-buy"].pair_key == "LOT|L-1"
    assert fields["t-buy"].pair_role == "still_open"
    assert fields["t-buy"].partner_trade_id is None
    assert fields["t-buy"].pair_cap == "top"


def test_partial_stock_lot_pair():
    buy = Trade(id="t-buy", account="Schwab/main", date=date(2026, 1, 10),
                ticker="AAPL", action="Buy", quantity=100.0, cost_basis=14800.0)
    sell1 = Trade(id="t-s1", account="Schwab/main", date=date(2026, 2, 1),
                  ticker="AAPL", action="Sell", quantity=30.0, proceeds=4500.0, cost_basis=None)
    sell2 = Trade(id="t-s2", account="Schwab/main", date=date(2026, 3, 1),
                  ticker="AAPL", action="Sell", quantity=70.0, proceeds=10800.0, cost_basis=None)
    lot = _lot_from_buy(buy, lot_id="L-1")
    rows = [FakeTimelineRow(trade=buy), FakeTimelineRow(trade=sell1), FakeTimelineRow(trade=sell2)]

    fields = compute_pair_fields(timeline_rows=rows, lots=[lot], open_lot_ids=set())

    assert fields["t-buy"].pair_key == fields["t-s1"].pair_key == fields["t-s2"].pair_key == "LOT|L-1"
    assert fields["t-buy"].pair_role == "open"
    assert fields["t-s1"].pair_role == "close"
    assert fields["t-s2"].pair_role == "close"
    assert fields["t-s1"].pair_position == (1, 2)
    assert fields["t-s2"].pair_position == (2, 2)
    assert fields["t-buy"].pair_cap == "top"
    assert fields["t-s2"].pair_cap == "bottom"


def test_multi_lot_sell_picks_primary_lot():
    buy1 = Trade(id="t-b1", account="Schwab/main", date=date(2026, 1, 1),
                 ticker="AAPL", action="Buy", quantity=100.0, cost_basis=14000.0)
    buy2 = Trade(id="t-b2", account="Schwab/main", date=date(2026, 2, 1),
                 ticker="AAPL", action="Buy", quantity=50.0, cost_basis=7500.0)
    sell = Trade(id="t-s", account="Schwab/main", date=date(2026, 3, 1),
                 ticker="AAPL", action="Sell", quantity=80.0, proceeds=12000.0, cost_basis=None)
    lot1 = _lot_from_buy(buy1, "L-1")
    lot2 = _lot_from_buy(buy2, "L-2")
    rows = [FakeTimelineRow(trade=buy1), FakeTimelineRow(trade=buy2), FakeTimelineRow(trade=sell)]

    fields = compute_pair_fields(timeline_rows=rows, lots=[lot1, lot2], open_lot_ids={"L-1", "L-2"})

    # SELL took 80 from lot1 (only lot consumed). Lot1 has 20 left → still open.
    assert fields["t-s"].pair_key == "LOT|L-1"
    assert fields["t-s"].multi_lot_overflow == 0


def test_multi_lot_sell_spans_two_lots():
    buy1 = Trade(id="t-b1", account="Schwab/main", date=date(2026, 1, 1),
                 ticker="AAPL", action="Buy", quantity=30.0, cost_basis=4200.0)
    buy2 = Trade(id="t-b2", account="Schwab/main", date=date(2026, 2, 1),
                 ticker="AAPL", action="Buy", quantity=100.0, cost_basis=15000.0)
    sell = Trade(id="t-s", account="Schwab/main", date=date(2026, 3, 1),
                 ticker="AAPL", action="Sell", quantity=80.0, proceeds=12000.0, cost_basis=None)
    lot1 = _lot_from_buy(buy1, "L-1")
    lot2 = _lot_from_buy(buy2, "L-2")
    rows = [FakeTimelineRow(trade=buy1), FakeTimelineRow(trade=buy2), FakeTimelineRow(trade=sell)]

    fields = compute_pair_fields(timeline_rows=rows, lots=[lot1, lot2], open_lot_ids={"L-2"})

    # SELL took 30 from lot1 + 50 from lot2. Primary = lot2 (50 > 30).
    assert fields["t-s"].pair_key == "LOT|L-2"
    assert fields["t-s"].multi_lot_overflow == 1
