"""Unit tests for centralized presentation formatters (§5.9 of spec)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from net_alpha.web.format import fmt_quantity


@pytest.mark.parametrize(
    "value,expected",
    [
        (Decimal("11"),       "11"),
        (Decimal("11.0"),     "11"),
        (Decimal("11.0000"),  "11"),
        (Decimal("0"),        "0"),
        (Decimal("0.5"),      "0.5"),
        (Decimal("0.1234"),   "0.1234"),
        (Decimal("0.12345"),  "0.1234"),     # banker's rounding to 4dp (5 falls between 4 and 5 → round to even = 4)
        (Decimal("1.5000"),   "1.5"),
        (Decimal("100.25"),   "100.25"),
        (Decimal("-3.5"),     "-3.5"),
        (Decimal("1000"),     "1000"),       # no thousands separator on quantity
    ],
)
def test_fmt_quantity_renders_integer_when_whole_else_up_to_4dp(value, expected):
    assert fmt_quantity(value) == expected


def test_fmt_quantity_accepts_int():
    assert fmt_quantity(11) == "11"


def test_fmt_quantity_accepts_float():
    assert fmt_quantity(0.5) == "0.5"


def test_fmt_quantity_none_returns_em_dash():
    assert fmt_quantity(None) == "—"
