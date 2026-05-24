from datetime import date
from decimal import Decimal

from net_alpha.models.domain import Lot, OptionDetails, Trade
from net_alpha.section_1256.classifier import classify_closed_trades
from net_alpha.section_1256.mtm import position_key

SPX = "SPX"


def _opt(strike, expiry, cp):
    return OptionDetails(strike=strike, expiry=expiry, call_put=cp)


def test_sell_after_mtm_uses_prior_year_mtm_as_basis():
    o = _opt(4000.0, date(2026, 6, 19), "C")
    buy = Trade(
        id="T_BUY",
        account="x",
        date=date(2024, 3, 1),
        ticker=SPX,
        action="Buy",
        quantity=1,
        proceeds=None,
        cost_basis=100,
        option_details=o,
        is_section_1256=True,
    )
    sell = Trade(
        id="T_SELL",
        account="x",
        date=date(2025, 4, 1),
        ticker=SPX,
        action="Sell",
        quantity=1,
        proceeds=180,
        cost_basis=None,
        option_details=o,
        is_section_1256=True,
    )
    # NOTE: Lot requires trade_id (Task 3 lesson). Mirror that pattern here.
    lot = Lot(
        id="L1",
        trade_id="T_BUY",
        account="x",
        date=date(2024, 3, 1),
        ticker=SPX,
        quantity=1,
        cost_basis=100,
        adjusted_basis=100,
        option_details=o,
    )

    pkey = position_key(account="x", ticker=SPX, option_details=o)

    def prior_basis(p, year):
        if p == pkey and year == 2024:
            return Decimal("150")
        return None

    out = classify_closed_trades([buy, sell], [lot], prior_year_mtm_basis_fn=prior_basis)
    assert len(out) == 1
    # realized = 180 (proceeds) − 150 (prior-year MTM basis) = 30
    assert out[0].realized_pnl == Decimal("30")
    assert out[0].long_term_portion == Decimal("18.00")
    assert out[0].short_term_portion == Decimal("12.00")


def test_no_prior_mtm_falls_back_to_lot_basis():
    o = _opt(4000.0, date(2026, 6, 19), "C")
    buy = Trade(
        id="T_BUY",
        account="x",
        date=date(2025, 3, 1),
        ticker=SPX,
        action="Buy",
        quantity=1,
        proceeds=None,
        cost_basis=100,
        option_details=o,
        is_section_1256=True,
    )
    sell = Trade(
        id="T_SELL",
        account="x",
        date=date(2025, 9, 1),
        ticker=SPX,
        action="Sell",
        quantity=1,
        proceeds=180,
        cost_basis=None,
        option_details=o,
        is_section_1256=True,
    )
    lot = Lot(
        id="L1",
        trade_id="T_BUY",
        account="x",
        date=date(2025, 3, 1),
        ticker=SPX,
        quantity=1,
        cost_basis=100,
        adjusted_basis=100,
        option_details=o,
    )

    def no_prior(_p, _y):
        return None

    out = classify_closed_trades([buy, sell], [lot], prior_year_mtm_basis_fn=no_prior)
    # Same-year sale, no prior MTM: basis = 100 (original).
    assert out[0].realized_pnl == Decimal("80")


def test_marked_qty_consumed_fifo_then_fresh_opens_use_lot_basis():
    """Audit #35: prior_year_mtm_basis_fn returns a per-contract FMV regardless
    of how many contracts were marked at EOY. If a long position is partially
    closed AFTER year-end and then fresh contracts of the same key are opened
    in the new year, the next sell can mix marked + fresh lots; the marked
    portion gets prior FMV but the fresh portion must use actual lot basis.

    Scenario:
        Year 1: BTO 10 contracts @ $5  (basis = $50)
        EOY MTM at $7/contract         (marked qty=10, FMV=$7)
        Year 2: STC 4 contracts        — consumes 4 marked at $7 = $28
        Year 2: BTO 5 fresh contracts @ $8 (basis = $40)
        Year 2: STC 7 contracts        — pulls 6 remaining marked + 1 fresh
                                         basis = 6 × $7 + 1 × $8 = $50

    Today's classifier would compute the second STC's basis as 7 × $7 = $49.
    """
    o = _opt(4000.0, date(2026, 6, 19), "C")
    buy_y1 = Trade(
        id="BUY_Y1",
        account="x",
        date=date(2024, 3, 1),
        ticker=SPX,
        action="Buy",
        quantity=10,
        proceeds=None,
        cost_basis=50,
        option_details=o,
        is_section_1256=True,
    )
    stc_y2_first = Trade(
        id="STC_Y2_1",
        account="x",
        date=date(2025, 1, 15),
        ticker=SPX,
        action="Sell",
        quantity=4,
        proceeds=28,
        cost_basis=None,
        option_details=o,
        is_section_1256=True,
    )
    bto_y2_fresh = Trade(
        id="BUY_Y2_FRESH",
        account="x",
        date=date(2025, 3, 1),
        ticker=SPX,
        action="Buy",
        quantity=5,
        proceeds=None,
        cost_basis=40,
        option_details=o,
        is_section_1256=True,
    )
    stc_y2_second = Trade(
        id="STC_Y2_2",
        account="x",
        date=date(2025, 6, 1),
        ticker=SPX,
        action="Sell",
        quantity=7,
        proceeds=70,
        cost_basis=None,
        option_details=o,
        is_section_1256=True,
    )
    lot_y1 = Lot(
        id="L_Y1",
        trade_id="BUY_Y1",
        account="x",
        date=date(2024, 3, 1),
        ticker=SPX,
        quantity=10,
        cost_basis=50,
        adjusted_basis=50,
        option_details=o,
    )
    lot_y2_fresh = Lot(
        id="L_Y2",
        trade_id="BUY_Y2_FRESH",
        account="x",
        date=date(2025, 3, 1),
        ticker=SPX,
        quantity=5,
        cost_basis=40,
        adjusted_basis=40,
        option_details=o,
    )

    pkey = position_key(account="x", ticker=SPX, option_details=o)

    def prior_basis(p, year):
        # EOY 2024 marked at $7 per contract.
        if p == pkey and year == 2024:
            return Decimal("7")
        return None

    out = classify_closed_trades(
        [buy_y1, stc_y2_first, bto_y2_fresh, stc_y2_second],
        [lot_y1, lot_y2_fresh],
        prior_year_mtm_basis_fn=prior_basis,
    )

    by_id = {c.trade_id: c for c in out}

    # First STC consumes 4 of the 10 marked at $7 each.
    assert by_id["STC_Y2_1"].realized_pnl == Decimal("0"), (
        f"STC_Y2_1 realized expected 0 (proceeds 28 - basis 4×$7=$28), got {by_id['STC_Y2_1'].realized_pnl}"
    )

    # Second STC consumes 6 remaining marked × $7 + 1 fresh × $8 = $50.
    # Proceeds 70, basis 50, realized = 20.
    assert by_id["STC_Y2_2"].realized_pnl == Decimal("20"), (
        f"STC_Y2_2 realized expected 20 (proceeds 70 - basis 6×$7+1×$8=$50), "
        f"got {by_id['STC_Y2_2'].realized_pnl} — the classifier is still "
        f"applying prior FMV to qty that was never marked"
    )


def test_legacy_call_without_prior_basis_fn_works():
    """Calling classify_closed_trades without the new arg uses lot basis (backwards-compat)."""
    o = _opt(4000.0, date(2026, 6, 19), "C")
    buy = Trade(
        id="T_BUY",
        account="x",
        date=date(2025, 3, 1),
        ticker=SPX,
        action="Buy",
        quantity=1,
        proceeds=None,
        cost_basis=100,
        option_details=o,
        is_section_1256=True,
    )
    sell = Trade(
        id="T_SELL",
        account="x",
        date=date(2025, 9, 1),
        ticker=SPX,
        action="Sell",
        quantity=1,
        proceeds=150,
        cost_basis=None,
        option_details=o,
        is_section_1256=True,
    )
    lot = Lot(
        id="L1",
        trade_id="T_BUY",
        account="x",
        date=date(2025, 3, 1),
        ticker=SPX,
        quantity=1,
        cost_basis=100,
        adjusted_basis=100,
        option_details=o,
    )
    out = classify_closed_trades([buy, sell], [lot])
    assert out[0].realized_pnl == Decimal("50")
