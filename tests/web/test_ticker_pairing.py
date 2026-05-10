"""Tests for the trade-pairing presentation-layer transform.

Each test exercises one rule from
docs/superpowers/specs/2026-05-10-ticker-trade-pairings-design.md.
"""
from __future__ import annotations

from datetime import date

import pytest

from net_alpha.web.pairing import PairFields, compute_pair_fields


def test_module_smoke_returns_empty_dict_for_no_rows():
    result = compute_pair_fields(timeline_rows=[], lots=[], open_lot_ids=set())
    assert result == {}
