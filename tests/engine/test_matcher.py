from datetime import date

from net_alpha.engine.matcher import is_within_wash_sale_window


def test_same_day():
    assert is_within_wash_sale_window(date(2024, 10, 15), date(2024, 10, 15)) is True


def test_exactly_30_days_before():
    assert is_within_wash_sale_window(date(2024, 10, 15), date(2024, 9, 15)) is True


def test_exactly_30_days_after():
    assert is_within_wash_sale_window(date(2024, 10, 15), date(2024, 11, 14)) is True


def test_31_days_before_outside_window():
    assert is_within_wash_sale_window(date(2024, 10, 15), date(2024, 9, 14)) is False


def test_31_days_after_outside_window():
    assert is_within_wash_sale_window(date(2024, 10, 15), date(2024, 11, 15)) is False


def test_1_day_before():
    assert is_within_wash_sale_window(date(2024, 10, 15), date(2024, 10, 14)) is True


def test_1_day_after():
    assert is_within_wash_sale_window(date(2024, 10, 15), date(2024, 10, 16)) is True


def test_cross_year_boundary():
    # Dec 20 sale, Jan 5 buy = 16 days → within window
    assert is_within_wash_sale_window(date(2024, 12, 20), date(2025, 1, 5)) is True


def test_cross_year_boundary_outside():
    # Dec 1 sale, Jan 31 buy = 61 days → outside window
    assert is_within_wash_sale_window(date(2024, 12, 1), date(2025, 1, 31)) is False
