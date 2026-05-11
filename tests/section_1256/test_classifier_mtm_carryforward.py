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
