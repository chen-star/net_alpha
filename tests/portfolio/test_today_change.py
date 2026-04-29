"""Phase 3: today_change compute for the Overview Today tile."""

from __future__ import annotations

from decimal import Decimal


def test_today_change_aggregates_signed_delta_across_lots():
    """today_change = sum((price - prev_close) * qty) across open lots."""
    from net_alpha.portfolio.positions import compute_today_change

    quotes = {
        "NVDA": (Decimal("210"), Decimal("200")),
        "HIMS": (Decimal("28"), Decimal("28.50")),
    }
    lots = [
        ("NVDA", Decimal("5")),
        ("HIMS", Decimal("100")),
    ]
    delta, prev_value = compute_today_change(lots, quotes)
    assert delta == Decimal("0")
    assert prev_value == Decimal("3850")


def test_today_change_skips_lots_without_previous_close():
    from net_alpha.portfolio.positions import compute_today_change

    quotes = {
        "NVDA": (Decimal("210"), None),
        "HIMS": (Decimal("28"), Decimal("28.50")),
    }
    lots = [
        ("NVDA", Decimal("5")),
        ("HIMS", Decimal("100")),
    ]
    delta, prev_value = compute_today_change(lots, quotes)
    assert delta == Decimal("-50")
    assert prev_value == Decimal("2850")
