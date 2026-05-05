"""Tests for portfolio.explain — math-explainer payload builders."""

from __future__ import annotations


def test_total_return_breakdown_decomposition_sums_to_total_return():
    from decimal import Decimal

    from net_alpha.portfolio.explain import build_total_return_breakdown

    b = build_total_return_breakdown(
        period_label="YTD 2026",
        ending_value=Decimal("63420.18"),
        starting_value=Decimal("50000.00"),
        contributions=Decimal("5000.00"),
        realized_in_period=Decimal("3210.00"),
        is_lifetime=False,
    )
    # 63420.18 - 50000 - 5000 = 8420.18
    assert b.total_return == Decimal("8420.18")
    # 8420.18 - 3210 = 5210.18
    assert b.delta_unrealized_residual == Decimal("5210.18")
    # Realized + Δ Unrealized = Total Return
    assert b.realized_in_period + b.delta_unrealized_residual == b.total_return


def test_total_return_breakdown_lifetime_starts_at_zero():
    from decimal import Decimal

    from net_alpha.portfolio.explain import build_total_return_breakdown

    b = build_total_return_breakdown(
        period_label="Lifetime",
        ending_value=Decimal("110000.00"),
        starting_value=Decimal("0"),
        contributions=Decimal("50000.00"),
        realized_in_period=Decimal("0"),
        is_lifetime=True,
    )
    assert b.total_return == Decimal("60000.00")
    assert b.is_lifetime is True


def test_build_unrealized_breakdown_long_stock_only():
    """Single AAPL position, no short options → long_subtotal populated, short empty."""
    import datetime as dt
    from decimal import Decimal

    from net_alpha.models.domain import Lot
    from net_alpha.portfolio.explain import build_unrealized_breakdown
    from net_alpha.pricing.provider import Quote

    today = dt.date(2026, 5, 3)
    long_lot = Lot(
        account="X",
        date=dt.date(2025, 6, 1),
        ticker="AAPL",
        quantity=10.0,
        cost_basis=1500.0,
        adjusted_basis=1500.0,
        trade_id="t1",
    )
    consumed = [(long_lot, Decimal("10"), Decimal("1500"))]
    prices = {
        "AAPL": Quote(
            symbol="AAPL",
            price=Decimal("180"),
            previous_close=Decimal("178"),
            as_of=dt.datetime(2026, 5, 3, 16, 0, tzinfo=dt.UTC),
            source="yahoo",
        ),
    }
    b = build_unrealized_breakdown(
        consumed=consumed,
        short_option_rows=[],
        prices=prices,
        as_of=today,
    )
    assert len(b.long_lines) == 1
    assert b.long_lines[0].unrealized == Decimal("300.00")
    assert b.long_subtotal == Decimal("300.00")
    assert b.short_option_lines == []
    assert b.short_subtotal == Decimal("0")
    assert b.total_unrealized == Decimal("300.00")
    assert b.excluded_count == 0


def test_build_unrealized_breakdown_short_put_otm():
    """Short put OTM contributes positive unrealized via time decay."""
    import datetime as dt
    from decimal import Decimal

    from net_alpha.portfolio.explain import build_unrealized_breakdown
    from net_alpha.portfolio.models import OpenShortOptionRow
    from net_alpha.pricing.provider import Quote

    today = dt.date(2026, 5, 3)
    short_put = OpenShortOptionRow(
        account="X",
        ticker="SPY",
        strike=500.0,
        expiry=dt.date(2026, 7, 2),
        call_put="P",
        qty_short=Decimal("1"),
        premium_received=Decimal("500"),
        opened_at=dt.date(2026, 4, 3),
    )
    prices = {
        "SPY": Quote(
            symbol="SPY",
            price=Decimal("520"),
            previous_close=Decimal("519"),
            as_of=dt.datetime(2026, 5, 3, 16, 0, tzinfo=dt.UTC),
            source="yahoo",
        ),
    }
    b = build_unrealized_breakdown(
        consumed=[],
        short_option_rows=[short_put],
        prices=prices,
        as_of=today,
    )
    assert len(b.short_option_lines) == 1
    line = b.short_option_lines[0]
    assert line.contracts == 1
    assert line.intrinsic_per_share == Decimal("0")
    # 500 * (60/90) = 333.33...
    # est_value_to_close = max(0, 333.33) * 1 * 100 = 333.33
    # unrealized = 500 - 333.33 = 166.67
    assert abs(line.unrealized - Decimal("166.67")) < Decimal("0.50")
    assert b.short_subtotal == line.unrealized
    assert b.total_unrealized == line.unrealized
    assert line.is_covered is False


def test_build_unrealized_breakdown_excluded_count_for_unpriced_lot():
    """Unpriced equity lot counts toward excluded_count, contributes 0."""
    import datetime as dt
    from decimal import Decimal

    from net_alpha.models.domain import Lot
    from net_alpha.portfolio.explain import build_unrealized_breakdown

    today = dt.date(2026, 5, 3)
    lot = Lot(
        account="X",
        date=dt.date(2025, 6, 1),
        ticker="WXYZ",
        quantity=5.0,
        cost_basis=400.0,
        adjusted_basis=400.0,
        trade_id="t9",
    )
    b = build_unrealized_breakdown(
        consumed=[(lot, Decimal("5"), Decimal("400"))],
        short_option_rows=[],
        prices={},
        as_of=today,
    )
    assert b.long_lines == []
    assert b.excluded_count == 1
    assert b.total_unrealized == Decimal("0")


def test_build_account_value_breakdown_cash_only_both_equations_zero_positions():
    """With only cash, Composition = cash; Source = net_contributed + 0 + 0; both equal."""
    import datetime as dt
    from decimal import Decimal

    from net_alpha.portfolio.explain import build_account_value_breakdown

    today = dt.date(2026, 5, 4)
    b = build_account_value_breakdown(
        consumed=[],
        short_option_rows=[],
        prices={},
        cash_balance=Decimal("10000.00"),
        net_contributed=Decimal("10000.00"),
        lifetime_realized_economic=Decimal("0"),
        missing_symbols=(),
        fetched_at=None,
        as_of=today,
    )
    assert b.cash_balance == Decimal("10000.00")
    assert b.long_stock_mv == Decimal("0")
    assert b.long_option_mv == Decimal("0")
    assert b.short_option_liability == Decimal("0")
    assert b.net_contributed == Decimal("10000.00")
    assert b.lifetime_realized_economic == Decimal("0")
    assert b.current_unrealized == Decimal("0")
    assert b.total_account_value == Decimal("10000.00")
    assert b.has_short_options is False
    assert b.missing_symbols == ()


def test_build_account_value_breakdown_long_stock_reconciles_both_equations():
    """Buy 10 AAPL @ $150 cost, now $180. Cash had $1500 paid out.
    Composition: $0 cash + $1800 stock = $1800.
    Source: $1500 contributed + $0 realized + $300 unrealized = $1800.
    Both equations must agree.
    """
    import datetime as dt
    from decimal import Decimal

    from net_alpha.models.domain import Lot
    from net_alpha.portfolio.explain import build_account_value_breakdown
    from net_alpha.pricing.provider import Quote

    today = dt.date(2026, 5, 4)
    long_lot = Lot(
        account="X",
        date=dt.date(2025, 6, 1),
        ticker="AAPL",
        quantity=10.0,
        cost_basis=1500.0,
        adjusted_basis=1500.0,
        trade_id="t1",
    )
    consumed = [(long_lot, Decimal("10"), Decimal("1500"))]
    prices = {
        "AAPL": Quote(
            symbol="AAPL",
            price=Decimal("180"),
            previous_close=Decimal("178"),
            as_of=dt.datetime(2026, 5, 3, 16, 0, tzinfo=dt.UTC),
            source="yahoo",
        ),
    }
    b = build_account_value_breakdown(
        consumed=consumed,
        short_option_rows=[],
        prices=prices,
        cash_balance=Decimal("0"),
        net_contributed=Decimal("1500"),
        lifetime_realized_economic=Decimal("0"),
        missing_symbols=(),
        fetched_at=None,
        as_of=today,
    )
    assert b.long_stock_mv == Decimal("1800.00")
    assert b.long_option_mv == Decimal("0")
    assert b.short_option_liability == Decimal("0")
    assert b.current_unrealized == Decimal("300.00")
    assert b.total_account_value == Decimal("1800.00")
    # Reconciliation: cash + long − short == net_contributed + realized + unrealized
    assert (
        b.cash_balance + b.long_stock_mv + b.long_option_mv - b.short_option_liability
        == b.net_contributed + b.lifetime_realized_economic + b.current_unrealized
    )


def test_build_account_value_breakdown_short_put_sets_has_short_options_and_subtracts_liability():
    """Short put OTM contributes a positive liability to subtract in
    Composition. has_short_options flag is set.
    """
    import datetime as dt
    from decimal import Decimal

    from net_alpha.portfolio.explain import build_account_value_breakdown
    from net_alpha.portfolio.models import OpenShortOptionRow
    from net_alpha.pricing.provider import Quote

    today = dt.date(2026, 5, 4)
    row = OpenShortOptionRow(
        account="X",
        ticker="SPY",
        strike=400.0,
        expiry=dt.date(2026, 6, 19),
        call_put="P",
        qty_short=Decimal("1"),
        premium_received=Decimal("200.00"),
        opened_at=dt.date(2026, 4, 4),
    )
    prices = {
        "SPY": Quote(
            symbol="SPY",
            price=Decimal("420"),
            previous_close=Decimal("418"),
            as_of=dt.datetime(2026, 5, 3, 16, 0, tzinfo=dt.UTC),
            source="yahoo",
        ),
    }
    b = build_account_value_breakdown(
        consumed=[],
        short_option_rows=[row],
        prices=prices,
        cash_balance=Decimal("400"),  # premium received ($200) + true net contributed ($200)
        net_contributed=Decimal("200"),  # true contributions; chosen so reconciliation holds
        lifetime_realized_economic=Decimal("0"),
        missing_symbols=(),
        fetched_at=None,
        as_of=today,
    )
    # OTM put @ spot 420 vs strike 400: intrinsic = 0; liability = time-decay only.
    assert b.has_short_options is True
    assert b.short_option_liability >= Decimal("0")
    # Reconciliation must hold (raises if not):
    assert (
        b.cash_balance + b.long_stock_mv + b.long_option_mv - b.short_option_liability
        == b.net_contributed + b.lifetime_realized_economic + b.current_unrealized
    )


def test_build_account_value_breakdown_unpriced_lot_carried_at_basis():
    """Unpriced equity lot is carried at cost basis (matches kpis.open_position_value
    fallback). Reconciliation still holds; missing_symbols flows through.
    """
    import datetime as dt
    from decimal import Decimal

    from net_alpha.models.domain import Lot
    from net_alpha.portfolio.explain import build_account_value_breakdown

    today = dt.date(2026, 5, 4)
    long_lot = Lot(
        account="X",
        date=dt.date(2025, 6, 1),
        ticker="UNPRICED",
        quantity=10.0,
        cost_basis=500.0,
        adjusted_basis=500.0,
        trade_id="t1",
    )
    consumed = [(long_lot, Decimal("10"), Decimal("500"))]
    b = build_account_value_breakdown(
        consumed=consumed,
        short_option_rows=[],
        prices={},  # no quote available
        cash_balance=Decimal("0"),
        net_contributed=Decimal("500"),
        lifetime_realized_economic=Decimal("0"),
        missing_symbols=("UNPRICED",),
        fetched_at=None,
        as_of=today,
    )
    assert b.long_stock_mv == Decimal("500.00")  # carried at basis
    assert b.current_unrealized == Decimal("0")  # market == cost
    assert b.total_account_value == Decimal("500.00")
    assert b.missing_symbols == ("UNPRICED",)
