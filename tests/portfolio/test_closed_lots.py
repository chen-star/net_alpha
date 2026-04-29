"""Unit tests for compute_closed_lots — Closed positions tab aggregator."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from net_alpha.models.realized_gl import RealizedGLLot
from net_alpha.portfolio.positions import compute_closed_lots


def _gl(
    *,
    ticker: str = "AAPL",
    account: str = "Schwab/Tax",
    closed: date = date(2026, 4, 1),
    opened: date = date(2026, 1, 1),
    qty: float = 10.0,
    proceeds: float = 1500.0,
    cost_basis: float = 1000.0,
    term: str = "Short Term",
    wash_sale: bool = False,
    disallowed_loss: float = 0.0,
    option_strike: float | None = None,
    option_expiry: str | None = None,
    option_call_put: str | None = None,
) -> RealizedGLLot:
    return RealizedGLLot(
        account_display=account,
        symbol_raw=ticker,
        ticker=ticker,
        closed_date=closed,
        opened_date=opened,
        quantity=qty,
        proceeds=proceeds,
        cost_basis=cost_basis,
        unadjusted_cost_basis=cost_basis,
        wash_sale=wash_sale,
        disallowed_loss=disallowed_loss,
        term=term,
        option_strike=option_strike,
        option_expiry=option_expiry,
        option_call_put=option_call_put,
    )


def test_realized_pl_is_proceeds_minus_basis():
    rows = compute_closed_lots([_gl(proceeds=1500.0, cost_basis=1000.0)])
    assert len(rows) == 1
    assert rows[0].realized_pl == Decimal("500")


def test_negative_realized_pl_for_loss_close():
    rows = compute_closed_lots([_gl(proceeds=800.0, cost_basis=1000.0)])
    assert rows[0].realized_pl == Decimal("-200")


def test_period_filter_includes_only_matching_year():
    lots = [
        _gl(closed=date(2025, 6, 1), proceeds=100, cost_basis=50),
        _gl(closed=date(2026, 6, 1), proceeds=200, cost_basis=50),
        _gl(closed=date(2027, 1, 5), proceeds=300, cost_basis=50),
    ]
    ytd = compute_closed_lots(lots, period=(2026, 2027))
    assert len(ytd) == 1
    assert ytd[0].closed_date.year == 2026


def test_period_none_returns_all_lots():
    lots = [
        _gl(closed=date(2024, 1, 1)),
        _gl(closed=date(2026, 1, 1)),
    ]
    rows = compute_closed_lots(lots, period=None)
    assert len(rows) == 2


def test_account_filter_drops_other_accounts():
    lots = [
        _gl(account="Schwab/Tax"),
        _gl(account="Schwab/Brokerage"),
    ]
    rows = compute_closed_lots(lots, account_display="Schwab/Tax")
    assert len(rows) == 1
    assert rows[0].account == "Schwab/Tax"


def test_sorted_by_close_date_descending():
    lots = [
        _gl(closed=date(2026, 1, 15)),
        _gl(closed=date(2026, 4, 1)),
        _gl(closed=date(2026, 2, 20)),
    ]
    rows = compute_closed_lots(lots)
    assert [r.closed_date for r in rows] == [
        date(2026, 4, 1),
        date(2026, 2, 20),
        date(2026, 1, 15),
    ]


def test_term_passes_through():
    rows = compute_closed_lots([_gl(term="Long Term")])
    assert rows[0].term == "Long Term"


def test_wash_sale_fields_pass_through():
    rows = compute_closed_lots(
        [_gl(wash_sale=True, disallowed_loss=42.5, proceeds=100, cost_basis=200)]
    )
    assert rows[0].wash_sale is True
    assert rows[0].disallowed_loss == Decimal("42.5")


def test_option_lot_display_symbol_includes_contract_details():
    rows = compute_closed_lots(
        [
            _gl(
                ticker="AAPL",
                option_strike=200.0,
                option_expiry="2026-06-19",
                option_call_put="C",
            )
        ]
    )
    assert rows[0].is_option is True
    assert rows[0].display_symbol == "AAPL CALL $200 2026-06-19"


def test_equity_lot_display_symbol_is_just_ticker():
    rows = compute_closed_lots([_gl(ticker="AAPL")])
    assert rows[0].is_option is False
    assert rows[0].display_symbol == "AAPL"


def test_empty_input_returns_empty_list():
    assert compute_closed_lots([]) == []
