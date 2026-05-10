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
