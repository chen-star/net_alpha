from datetime import date
from decimal import Decimal

import pytest

from net_alpha.engine.lot_selector import (
    InsufficientLotsError,
    LotPick,  # noqa: F401 — re-export sanity check
    LotPickResult,
    select_lots,
)


def _lot(id: int, qty: float, basis: float, acquired: date):
    """Build a minimal Lot domain object for tests."""
    from net_alpha.models.domain import Lot

    return Lot(
        id=str(id),
        trade_id=f"t{id}",
        ticker="SPY",
        date=acquired,
        quantity=qty,
        cost_basis=basis,
        adjusted_basis=basis,
        account="default",
    )


def test_insufficient_lots_raises():
    lots = [_lot(1, 10, 1000, date(2024, 1, 1))]
    with pytest.raises(InsufficientLotsError):
        select_lots(
            lots=lots,
            qty=Decimal("100"),
            sell_price=Decimal("110"),
            sell_date=date(2026, 5, 5),
            strategy="FIFO",
            repo=None,
            etf_pairs={},
            brackets=None,
            carryforward=None,
        )


def test_lot_pick_result_has_required_fields():
    # 100-share lot with $50/share total basis ($5000 total), partial-fill 50 shares.
    # LotPick.adjusted_basis is per-share, so 5000 / 100 = $50/sh and the
    # 50-share partial fill realizes 50 * (100 - 50) = $2500.
    lots = [_lot(1, 100, 5000.0, date(2024, 1, 1))]
    result = select_lots(
        lots=lots,
        qty=Decimal("50"),
        sell_price=Decimal("100"),
        sell_date=date(2026, 5, 5),
        strategy="FIFO",
        repo=None,
        etf_pairs={},
        brackets=None,
        carryforward=None,
    )
    assert isinstance(result, LotPickResult)
    assert result.strategy == "FIFO"
    assert len(result.picks) == 1
    assert result.picks[0].qty_consumed == Decimal("50")
    assert result.picks[0].adjusted_basis == Decimal("50")  # per-share
    assert result.pre_tax_pnl == Decimal("2500")  # 50 * (100 - 50)
    assert result.has_wash_sale_risk is False
    assert result.wash_sale_disallowed == Decimal("0")


def _make_lots():
    """3 same-size lots with distinct dates and basis-per-share."""
    return [
        _lot(1, 100, 8000.0, date(2023, 1, 15)),  # oldest, low basis ($80/sh)
        _lot(2, 100, 12000.0, date(2024, 6, 1)),  # mid, high basis ($120/sh)
        _lot(3, 100, 10000.0, date(2025, 3, 1)),  # newest, mid basis ($100/sh)
    ]


def _strategy_pick_ids(strategy: str) -> list[str]:
    lots = _make_lots()
    result = select_lots(
        lots=lots,
        qty=Decimal("150"),
        sell_price=Decimal("110"),
        sell_date=date(2026, 5, 5),
        strategy=strategy,
        repo=None,
        etf_pairs={},
        brackets=None,
        carryforward=None,
    )
    return [p.lot_id for p in result.picks]


def test_fifo_consumes_oldest_first():
    assert _strategy_pick_ids("FIFO") == ["1", "2"]


def test_lifo_consumes_newest_first():
    assert _strategy_pick_ids("LIFO") == ["3", "2"]


def test_hifo_consumes_highest_basis_first():
    assert _strategy_pick_ids("HIFO") == ["2", "3"]


def test_hifo_sorts_on_basis_per_share_not_total_basis():
    """A small lot with high $/share should win over a large lot with low $/share,
    even though the large lot has higher TOTAL basis. This is the correctness fix
    from Task 11 review."""
    lots = [
        _lot(1, 1000, 50000.0, date(2024, 1, 1)),  # 1000 sh @ $50/sh, total $50K
        _lot(2, 10, 2000.0, date(2024, 1, 2)),  # 10 sh @ $200/sh, total $2K
    ]
    result = select_lots(
        lots=lots,
        qty=Decimal("10"),
        sell_price=Decimal("110"),
        sell_date=date(2026, 5, 5),
        strategy="HIFO",
        repo=None,
        etf_pairs={},
        brackets=None,
        carryforward=None,
    )
    # HIFO should pick lot 2 first (higher per-share basis).
    assert [p.lot_id for p in result.picks] == ["2"]


def test_hifo_tiebreak_deterministic():
    """Two lots with identical basis-per-share → tiebreak by lot_id ascending."""
    lots = [
        _lot(2, 100, 10000.0, date(2024, 1, 1)),  # $100/sh
        _lot(1, 100, 10000.0, date(2025, 1, 1)),  # $100/sh — same per-share
    ]
    result = select_lots(
        lots=lots,
        qty=Decimal("100"),
        sell_price=Decimal("110"),
        sell_date=date(2026, 5, 5),
        strategy="HIFO",
        repo=None,
        etf_pairs={},
        brackets=None,
        carryforward=None,
    )
    # Tiebreak by lot_id ascending: "1" wins.
    assert result.picks[0].lot_id == "1"


def test_fifo_tiebreak_by_lot_id_when_same_date():
    lots = [
        _lot(2, 50, 5000.0, date(2024, 1, 1)),
        _lot(1, 50, 5000.0, date(2024, 1, 1)),
    ]
    result = select_lots(
        lots=lots,
        qty=Decimal("50"),
        sell_price=Decimal("110"),
        sell_date=date(2026, 5, 5),
        strategy="FIFO",
        repo=None,
        etf_pairs={},
        brackets=None,
        carryforward=None,
    )
    assert result.picks[0].lot_id == "1"


def test_wash_sale_flagged_when_existing_buy_within_30_days():
    """A loss lot with a recent buy in the ±30d window should be flagged."""
    from datetime import date as D

    from net_alpha.models.domain import Trade

    lots = [_lot(1, 100, 15000.0, D(2024, 6, 1))]  # basis $15K total, $150/sh

    # Stub repo with a buy 10 days before the proposed sell.
    class _R:
        def trades_for_ticker_in_window(self, ticker, sell_date, days):
            return [
                Trade(
                    id="b1",
                    account="default",
                    ticker="SPY",
                    date=D(2026, 4, 25),
                    action="Buy",
                    quantity=10,
                    proceeds=None,
                    cost_basis=1100.0,
                )
            ]

    result = select_lots(
        lots=lots,
        qty=Decimal("100"),
        sell_price=Decimal("100"),
        sell_date=D(2026, 5, 5),
        strategy="FIFO",
        repo=_R(),
        etf_pairs={},
        brackets=None,
        carryforward=None,
    )
    assert result.has_wash_sale_risk is True
    # Loss = (100 - 150) * 100 = -5000. Wash sale disallows the loss magnitude.
    assert result.wash_sale_disallowed == Decimal("5000")


def test_no_wash_sale_when_loss_lot_has_no_replacement_buy():
    from datetime import date as D

    lots = [_lot(1, 100, 15000.0, D(2024, 6, 1))]

    class _R:
        def trades_for_ticker_in_window(self, ticker, sell_date, days):
            return []

    result = select_lots(
        lots=lots,
        qty=Decimal("100"),
        sell_price=Decimal("100"),
        sell_date=D(2026, 5, 5),
        strategy="FIFO",
        repo=_R(),
        etf_pairs={},
        brackets=None,
        carryforward=None,
    )
    assert result.has_wash_sale_risk is False
    assert result.wash_sale_disallowed == Decimal("0")


def test_no_wash_sale_when_lot_is_a_gain():
    """Gains can't trigger wash sales."""
    from datetime import date as D

    from net_alpha.models.domain import Trade

    lots = [_lot(1, 100, 5000.0, D(2024, 6, 1))]  # basis $50/sh, sell at $100 = gain

    class _R:
        def trades_for_ticker_in_window(self, ticker, sell_date, days):
            return [
                Trade(
                    id="b1",
                    account="default",
                    ticker="SPY",
                    date=D(2026, 4, 25),
                    action="Buy",
                    quantity=10,
                    proceeds=None,
                    cost_basis=1100.0,
                )
            ]

    result = select_lots(
        lots=lots,
        qty=Decimal("100"),
        sell_price=Decimal("100"),
        sell_date=D(2026, 5, 5),
        strategy="FIFO",
        repo=_R(),
        etf_pairs={},
        brackets=None,
        carryforward=None,
    )
    assert result.has_wash_sale_risk is False


def test_after_tax_applies_brackets_and_carryforward():
    from datetime import date as D
    from decimal import Decimal as Dc

    from net_alpha.portfolio.carryforward import Carryforward
    from net_alpha.portfolio.tax_planner import TaxBrackets

    # Lot held > 365 days at $50/sh, sell at $100 → LT gain $5000.
    # 100 shares × $50/share basis = $5000 total. _lot expects total basis.
    lots = [_lot(1, 100, 5000.0, D(2023, 1, 1))]
    brackets = TaxBrackets(
        filing_status="single",
        state="",
        federal_marginal_rate=Dc("0.35"),
        state_marginal_rate=Dc("0"),
        ltcg_rate=Dc("0.15"),
        qualified_div_rate=Dc("0.15"),
        niit_enabled=False,
    )
    cf = Carryforward(st=Dc("0"), lt=Dc("2000"), source="user")

    class _R:
        def trades_for_ticker_in_window(self, *a, **kw):
            return []

    result = select_lots(
        lots=lots,
        qty=Dc("100"),
        sell_price=Dc("100"),
        sell_date=D(2026, 5, 5),
        strategy="FIFO",
        repo=_R(),
        etf_pairs={},
        brackets=brackets,
        carryforward=cf,
    )
    # Pre-tax LT gain: 100 * (100 - 50) = 5000
    # After $2000 LT carryforward: taxable LT = 3000
    # Tax: 3000 * 0.15 = 450
    # After-tax: 5000 - 450 = 4550
    assert result.pre_tax_pnl == Dc("5000")
    assert result.after_tax_pnl == Dc("4550")


def test_after_tax_disallowed_loss_treated_as_zero_benefit():
    """A wash-sale-disallowed loss provides $0 current-year tax benefit."""
    from datetime import date as D
    from decimal import Decimal as Dc

    from net_alpha.models.domain import Trade
    from net_alpha.portfolio.tax_planner import TaxBrackets

    # 100 shares, $150/sh basis ($15K total), sell at $100 → -$5000 loss.
    lots = [_lot(1, 100, 15000.0, D(2024, 6, 1))]
    brackets = TaxBrackets(
        filing_status="single",
        state="",
        federal_marginal_rate=Dc("0.35"),
        state_marginal_rate=Dc("0"),
        ltcg_rate=Dc("0.15"),
        qualified_div_rate=Dc("0.15"),
        niit_enabled=False,
    )

    class _R:
        def trades_for_ticker_in_window(self, *a, **kw):
            return [
                Trade(
                    id="b1",
                    account="default",
                    ticker="SPY",
                    date=D(2026, 4, 25),
                    action="Buy",
                    quantity=10,
                    proceeds=None,
                    cost_basis=1100.0,
                )
            ]

    result = select_lots(
        lots=lots,
        qty=Dc("100"),
        sell_price=Dc("100"),
        sell_date=D(2026, 5, 5),
        strategy="FIFO",
        repo=_R(),
        etf_pairs={},
        brackets=brackets,
        carryforward=None,
    )
    # Pre-tax: -5000. Wash sale disallows the full loss → 0 current-year benefit.
    # After-tax: pre_tax - tax_bill (0) - loss_benefit (0) = -5000
    assert result.pre_tax_pnl == Dc("-5000")
    assert result.wash_sale_disallowed == Dc("5000")
    assert result.after_tax_pnl == Dc("-5000")


def test_after_tax_no_brackets_falls_back_to_pretax_with_note():
    from datetime import date as D
    from decimal import Decimal as Dc

    lots = [_lot(1, 100, 5000.0, D(2023, 1, 1))]

    class _R:
        def trades_for_ticker_in_window(self, *a, **kw):
            return []

    result = select_lots(
        lots=lots,
        qty=Dc("100"),
        sell_price=Dc("100"),
        sell_date=D(2026, 5, 5),
        strategy="MIN_TAX",
        repo=_R(),
        etf_pairs={},
        brackets=None,
        carryforward=None,
    )
    assert result.after_tax_pnl == result.pre_tax_pnl
    assert any("brackets" in n.lower() for n in result.notes)
