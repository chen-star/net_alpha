"""Tests for the trade-pairing presentation-layer transform.

Each test exercises one rule from
docs/superpowers/specs/2026-05-10-ticker-trade-pairings-design.md.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest

from net_alpha.models.domain import OptionDetails, Trade
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
