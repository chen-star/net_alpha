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


from net_alpha.web.format import fmt_currency


@pytest.mark.parametrize(
    "amount,density,expected",
    [
        (Decimal("0"),         "comfortable", "$0.00"),
        (Decimal("12.5"),      "comfortable", "$12.50"),
        (Decimal("1234.56"),   "comfortable", "$1,234.56"),
        (Decimal("1000000"),   "comfortable", "$1,000,000.00"),
        (Decimal("-50.25"),    "comfortable", "-$50.25"),
        # Compact + ≥ $10k → 0dp
        (Decimal("9999.99"),   "compact",     "$9,999.99"),
        (Decimal("10000"),     "compact",     "$10,000"),
        (Decimal("12345.67"),  "compact",     "$12,346"),
        (Decimal("-12345.67"), "compact",     "-$12,346"),
        # Tax-view follows comfortable (always 2dp)
        (Decimal("12345.67"),  "tax-view",    "$12,345.67"),
    ],
)
def test_fmt_currency_density_aware(amount, density, expected):
    assert fmt_currency(amount, density=density) == expected


def test_fmt_currency_default_density_is_comfortable():
    assert fmt_currency(Decimal("12345.67")) == "$12,345.67"


def test_fmt_currency_none_returns_em_dash():
    assert fmt_currency(None) == "—"


def test_fmt_currency_unknown_density_falls_back_to_comfortable():
    # Future-proofing: never raise; never silently swallow values.
    assert fmt_currency(Decimal("12345.67"), density="bogus") == "$12,345.67"


from net_alpha.web.format import fmt_percent


@pytest.mark.parametrize(
    "value,expected",
    [
        (Decimal("0"),       "0.0%"),
        (Decimal("0.354"),   "35.4%"),       # input is fractional (0.354 = 35.4%)
        (Decimal("1.0"),     "100.0%"),
        (Decimal("-0.054"),  "-5.4%"),
        (Decimal("0.00499"), "0.5%"),        # banker's rounding, halves to even
        (Decimal("0.0001"),  "0.0%"),
        (Decimal("1.234"),   "123.4%"),
    ],
)
def test_fmt_percent_one_decimal(value, expected):
    assert fmt_percent(value) == expected


def test_fmt_percent_none_returns_em_dash():
    assert fmt_percent(None) == "—"


def test_fmt_percent_accepts_int():
    assert fmt_percent(0) == "0.0%"
