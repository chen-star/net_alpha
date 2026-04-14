"""Integration tests: wash sale detection engine with real temp DB."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from net_alpha.db.repository import TradeRepository
from net_alpha.engine.detector import detect_wash_sales
from net_alpha.models.domain import OptionDetails, Trade

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _trade(
    ticker: str,
    action: str,
    trade_date: date,
    quantity: float,
    proceeds: float | None = None,
    cost_basis: float | None = None,
    account: str = "Schwab",
    option_details: OptionDetails | None = None,
    basis_unknown: bool = False,
) -> Trade:
    return Trade(
        id=str(uuid4()),
        account=account,
        date=trade_date,
        ticker=ticker,
        action=action,
        quantity=quantity,
        proceeds=proceeds,
        cost_basis=cost_basis,
        basis_unknown=basis_unknown,
        option_details=option_details,
    )


def _loss_sell(ticker, trade_date, quantity=10.0, proceeds=2000.0, cost_basis=3000.0, account="Schwab", **kw):
    return _trade(ticker, "Sell", trade_date, quantity, proceeds=proceeds, cost_basis=cost_basis, account=account, **kw)


def _buy(ticker, trade_date, quantity=10.0, cost_basis=2200.0, account="Schwab", **kw):
    return _trade(ticker, "Buy", trade_date, quantity, cost_basis=cost_basis, account=account, **kw)


def _run(temp_db, trades: list[Trade], etf_pairs: dict):
    """Save trades to real DB, reload them, run detect_wash_sales, return DetectionResult."""
    engine, session, _ = temp_db
    TradeRepository(session).save_batch(trades)
    session.commit()
    loaded = TradeRepository(session).list_all()
    return detect_wash_sales(loaded, etf_pairs)


# ---------------------------------------------------------------------------
# Basic confirmed equity wash sale
# ---------------------------------------------------------------------------


def test_equity_confirmed(temp_db, etf_pairs):
    """TSLA sell loss Jan 10 + TSLA buy Jan 15 → Confirmed, disallowed=$1000."""
    sell = _loss_sell("TSLA", date(2024, 1, 10))
    buy = _buy("TSLA", date(2024, 1, 15))

    result = _run(temp_db, [sell, buy], etf_pairs)

    assert len(result.violations) == 1
    v = result.violations[0]
    assert v.confidence == "Confirmed"
    assert v.disallowed_loss == pytest.approx(1000.0)


# ---------------------------------------------------------------------------
# Day-boundary tests
# ---------------------------------------------------------------------------


def test_day_30_boundary_inclusive(temp_db, etf_pairs):
    """Sell Jan 1, buy Jan 31 = exactly 30 days → violation (inclusive)."""
    result = _run(
        temp_db,
        [
            _loss_sell("AAPL", date(2024, 1, 1)),
            _buy("AAPL", date(2024, 1, 31)),
        ],
        etf_pairs,
    )
    assert len(result.violations) == 1


def test_day_31_boundary_exclusive(temp_db, etf_pairs):
    """Sell Jan 1, buy Feb 1 = 31 days → no violation (exclusive)."""
    result = _run(
        temp_db,
        [
            _loss_sell("AAPL", date(2024, 1, 1)),
            _buy("AAPL", date(2024, 2, 1)),
        ],
        etf_pairs,
    )
    assert len(result.violations) == 0


# ---------------------------------------------------------------------------
# Cross-year window
# ---------------------------------------------------------------------------


def test_cross_year_window(temp_db, etf_pairs):
    """Sell Dec 15 2024, buy Jan 5 2025 (21 days) → violation crosses year boundary."""
    result = _run(
        temp_db,
        [
            _loss_sell("MSFT", date(2024, 12, 15)),
            _buy("MSFT", date(2025, 1, 5)),
        ],
        etf_pairs,
    )
    assert len(result.violations) == 1
    assert result.violations[0].confidence == "Confirmed"


# ---------------------------------------------------------------------------
# No violation cases
# ---------------------------------------------------------------------------


def test_no_violation_profit_sale(temp_db, etf_pairs):
    """Sell at profit (proceeds > cost_basis) + buy same week → no wash sale."""
    result = _run(
        temp_db,
        [
            _trade("TSLA", "Sell", date(2024, 1, 10), 10.0, proceeds=3500.0, cost_basis=2000.0),
            _buy("TSLA", date(2024, 1, 12)),
        ],
        etf_pairs,
    )
    assert len(result.violations) == 0


def test_basis_unknown_not_matched(temp_db, etf_pairs):
    """Sell with basis_unknown=True + buy same week → no violation."""
    result = _run(
        temp_db,
        [
            _trade("TSLA", "Sell", date(2024, 1, 10), 10.0, proceeds=2000.0, basis_unknown=True),
            _buy("TSLA", date(2024, 1, 12)),
        ],
        etf_pairs,
    )
    assert len(result.violations) == 0


# ---------------------------------------------------------------------------
# Cross-account
# ---------------------------------------------------------------------------


def test_equity_confirmed_cross_account(temp_db, etf_pairs):
    """TSLA sell Schwab + TSLA buy Robinhood, 5 days apart → Confirmed."""
    result = _run(
        temp_db,
        [
            _loss_sell("TSLA", date(2024, 1, 10), account="Schwab"),
            _buy("TSLA", date(2024, 1, 15), account="Robinhood"),
        ],
        etf_pairs,
    )
    assert len(result.violations) == 1
    assert result.violations[0].confidence == "Confirmed"


# ---------------------------------------------------------------------------
# Confidence levels
# ---------------------------------------------------------------------------


def test_equity_to_call_probable(temp_db, etf_pairs):
    """TSLA equity sell loss + TSLA call buy 10 days later → Probable."""
    result = _run(
        temp_db,
        [
            _loss_sell("TSLA", date(2024, 1, 10)),
            _buy(
                "TSLA",
                date(2024, 1, 20),
                option_details=OptionDetails(strike=250.0, expiry=date(2024, 3, 15), call_put="C"),
            ),
        ],
        etf_pairs,
    )
    assert len(result.violations) == 1
    assert result.violations[0].confidence == "Probable"


def test_sold_put_unclear(temp_db, etf_pairs):
    """TSLA equity sell loss + TSLA short put 5 days later → Unclear."""
    result = _run(
        temp_db,
        [
            _loss_sell("TSLA", date(2024, 1, 10)),
            _trade(
                "TSLA",
                "Sell",
                date(2024, 1, 15),
                5.0,
                proceeds=300.0,
                cost_basis=0.0,
                option_details=OptionDetails(strike=240.0, expiry=date(2024, 3, 15), call_put="P"),
            ),
        ],
        etf_pairs,
    )
    assert len(result.violations) == 1
    assert result.violations[0].confidence == "Unclear"


def test_etf_substantially_identical(temp_db, etf_pairs):
    """SPY sell loss + VOO buy 7 days later → Unclear (same sp500 group)."""
    result = _run(
        temp_db,
        [
            _loss_sell("SPY", date(2024, 1, 10)),
            _buy("VOO", date(2024, 1, 17)),
        ],
        etf_pairs,
    )
    assert len(result.violations) == 1
    assert result.violations[0].confidence == "Unclear"


# ---------------------------------------------------------------------------
# Partial FIFO allocation
# ---------------------------------------------------------------------------


def test_partial_fifo_allocation(temp_db, etf_pairs):
    """
    Loss: 10 shares.
    Lot A (before sell): 4 shares → fully consumed.
    Lot B (after sell): 10 shares → 6 shares consumed.
    Total matched = 10 shares; matched_quantities = [4, 6].
    """
    sell = _loss_sell("TSLA", date(2024, 1, 10), quantity=10.0, proceeds=2000.0, cost_basis=3000.0)
    lot_a = _buy("TSLA", date(2024, 1, 5), quantity=4.0, cost_basis=880.0)  # before sell → FIFO first
    lot_b = _buy("TSLA", date(2024, 1, 15), quantity=10.0, cost_basis=2200.0)  # after sell

    result = _run(temp_db, [sell, lot_a, lot_b], etf_pairs)

    assert len(result.violations) == 2
    total_matched = sum(v.matched_quantity for v in result.violations)
    assert total_matched == pytest.approx(10.0)
    quantities = sorted(v.matched_quantity for v in result.violations)
    assert quantities == pytest.approx([4.0, 6.0])


# ---------------------------------------------------------------------------
# Adjusted basis
# ---------------------------------------------------------------------------


def test_lot_adjusted_basis_updated(temp_db, etf_pairs):
    """
    Loss sale: 10 shares, $1000 loss.
    Replacement buy: cost_basis=$2200.
    After wash sale: replacement lot.adjusted_basis = 2200 + 1000 = 3200.
    """
    sell = _loss_sell("TSLA", date(2024, 1, 10), quantity=10.0, proceeds=2000.0, cost_basis=3000.0)
    buy = _buy("TSLA", date(2024, 1, 15), quantity=10.0, cost_basis=2200.0)

    result = _run(temp_db, [sell, buy], etf_pairs)

    assert len(result.violations) == 1
    assert result.violations[0].disallowed_loss == pytest.approx(1000.0)

    replacement_lot = next(lot for lot in result.lots if lot.trade_id == result.violations[0].replacement_trade_id)
    assert replacement_lot.adjusted_basis == pytest.approx(3200.0)


# ---------------------------------------------------------------------------
# Multiple loss sales: FIFO across shared lot pool
# ---------------------------------------------------------------------------


def test_multiple_loss_sales_fifo(temp_db, etf_pairs):
    """
    Two loss sales (Jan 5 and Jan 6), one shared buy lot (Jan 10, 10 shares).
    First loss by date (Jan 5) claims 6 shares; second (Jan 6) gets remaining 4.
    No lot allocated beyond its quantity.
    """
    sell1 = _loss_sell("TSLA", date(2024, 1, 5), quantity=6.0, proceeds=1200.0, cost_basis=1800.0)
    sell2 = _loss_sell("TSLA", date(2024, 1, 6), quantity=8.0, proceeds=1600.0, cost_basis=2400.0)
    shared_buy = _buy("TSLA", date(2024, 1, 10), quantity=10.0, cost_basis=2200.0)

    result = _run(temp_db, [sell1, sell2, shared_buy], etf_pairs)

    total_matched = sum(v.matched_quantity for v in result.violations)
    assert total_matched == pytest.approx(10.0)

    for lot in result.lots:
        allocated = sum(v.matched_quantity for v in result.violations if v.replacement_trade_id == lot.trade_id)
        assert allocated <= lot.quantity + 1e-9
