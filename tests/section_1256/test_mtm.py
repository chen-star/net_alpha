from datetime import date
from decimal import Decimal

from net_alpha.models.domain import Lot, OptionDetails, Trade
from net_alpha.section_1256.mtm import (
    mark_to_market,
    open_section_1256_positions,
    position_key,
)

SPX = "SPX"
UNIVERSE = {"SPX", "NDX"}


def _opt(strike, expiry, cp):
    return OptionDetails(strike=strike, expiry=expiry, call_put=cp)


def test_position_key_is_stable():
    o = _opt(4000.0, date(2026, 6, 19), "C")
    k1 = position_key(account="fidelity", ticker="SPX", option_details=o)
    k2 = position_key(account="fidelity", ticker="SPX", option_details=o)
    assert k1 == k2
    assert k1 != position_key(account="schwab", ticker="SPX", option_details=o)


def test_no_open_position_when_opened_and_closed_same_year():
    o = _opt(4000.0, date(2026, 6, 19), "C")
    buy = Trade(
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
        account="x",
        date=date(2025, 9, 1),
        ticker=SPX,
        action="Sell",
        quantity=1,
        proceeds=120,
        cost_basis=None,
        option_details=o,
        is_section_1256=True,
    )
    lot = Lot(
        id="L1",
        trade_id="T1",
        account="x",
        date=date(2025, 3, 1),
        ticker=SPX,
        quantity=1,
        adjusted_basis=100,
        option_details=o,
        cost_basis=100,
    )
    positions = open_section_1256_positions([buy, sell], [lot], UNIVERSE, as_of=date(2025, 12, 31))
    assert positions == []


def test_open_long_call_at_year_end():
    o = _opt(4000.0, date(2026, 6, 19), "C")
    buy = Trade(
        account="x",
        date=date(2025, 3, 1),
        ticker=SPX,
        action="Buy",
        quantity=2,
        proceeds=None,
        cost_basis=200,
        option_details=o,
        is_section_1256=True,
    )
    lot = Lot(
        id="L1",
        trade_id="T1",
        account="x",
        date=date(2025, 3, 1),
        ticker=SPX,
        quantity=2,
        adjusted_basis=200,
        option_details=o,
        cost_basis=200,
    )
    positions = open_section_1256_positions([buy], [lot], UNIVERSE, as_of=date(2025, 12, 31))
    assert len(positions) == 1
    pos = positions[0]
    assert pos.quantity == Decimal("2")
    assert pos.basis == Decimal("200")
    assert pos.ticker == "SPX"


def test_partial_close_leaves_remaining_open():
    o = _opt(4000.0, date(2026, 6, 19), "C")
    buy = Trade(
        account="x",
        date=date(2025, 3, 1),
        ticker=SPX,
        action="Buy",
        quantity=3,
        proceeds=None,
        cost_basis=300,
        option_details=o,
        is_section_1256=True,
    )
    sell = Trade(
        account="x",
        date=date(2025, 9, 1),
        ticker=SPX,
        action="Sell",
        quantity=1,
        proceeds=120,
        cost_basis=None,
        option_details=o,
        is_section_1256=True,
    )
    lot = Lot(
        id="L1",
        trade_id="T1",
        account="x",
        date=date(2025, 3, 1),
        ticker=SPX,
        quantity=3,
        adjusted_basis=300,
        option_details=o,
        cost_basis=300,
    )
    positions = open_section_1256_positions([buy, sell], [lot], UNIVERSE, as_of=date(2025, 12, 31))
    assert len(positions) == 1
    assert positions[0].quantity == Decimal("2")
    assert positions[0].basis == Decimal("200")


def test_non_1256_underlying_skipped():
    o = _opt(150.0, date(2026, 6, 19), "C")
    buy = Trade(
        account="x",
        date=date(2025, 3, 1),
        ticker="AAPL",
        action="Buy",
        quantity=1,
        proceeds=None,
        cost_basis=10,
        option_details=o,
        is_section_1256=False,
    )
    lot = Lot(
        id="L1",
        trade_id="T1",
        account="x",
        date=date(2025, 3, 1),
        ticker="AAPL",
        quantity=1,
        adjusted_basis=10,
        option_details=o,
        cost_basis=10,
    )
    positions = open_section_1256_positions([buy], [lot], UNIVERSE, as_of=date(2025, 12, 31))
    assert positions == []


def test_short_option_open_no_lot_row():
    """Short options have no Lot row — tracked via the trade ledger."""
    o = _opt(4000.0, date(2026, 6, 19), "P")
    sto = Trade(
        account="x",
        date=date(2025, 3, 1),
        ticker=SPX,
        action="Sell",
        quantity=1,
        proceeds=50,
        cost_basis=None,
        option_details=o,
        is_section_1256=True,
    )
    positions = open_section_1256_positions([sto], [], UNIVERSE, as_of=date(2025, 12, 31))
    assert len(positions) == 1
    assert positions[0].quantity == Decimal("-1")
    assert positions[0].basis == Decimal("-50")


def _fmv_fn_factory(price_map):
    def fn(ticker, opt, year):
        return price_map.get(
            (ticker, opt.strike, opt.expiry.isoformat(), opt.call_put, year),
            (None, "missing"),
        )

    return fn


def _no_prior_mtm(_pos_key, _year):
    return None


def test_mtm_emits_60_40_split_for_long_position_at_gain():
    o = _opt(4000.0, date(2026, 6, 19), "C")
    buy = Trade(
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
    lot = Lot(
        id="L1",
        trade_id="T1",
        account="x",
        date=date(2025, 3, 1),
        ticker=SPX,
        quantity=1,
        adjusted_basis=100,
        option_details=o,
        cost_basis=100,
    )
    fmv_fn = _fmv_fn_factory({(SPX, 4000.0, "2026-06-19", "C", 2025): (Decimal("150"), "yahoo_close")})
    out = mark_to_market(
        trades=[buy],
        lots=[lot],
        universe=UNIVERSE,
        tax_year=2025,
        fmv_fn=fmv_fn,
        prior_year_mtm_basis_fn=_no_prior_mtm,
    )
    assert len(out) == 1
    m = out[0]
    assert m.fmv == Decimal("150")
    assert m.basis_before == Decimal("100")
    assert m.unrealized_pnl == Decimal("50")
    assert m.long_term_portion == Decimal("30.00")
    assert m.short_term_portion == Decimal("20.00")
    assert m.fmv_source == "yahoo_close"
    assert m.tax_year == 2025


def test_mtm_uses_prior_year_basis_when_present():
    o = _opt(4000.0, date(2027, 6, 19), "C")
    buy = Trade(
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
    lot = Lot(
        id="L1",
        trade_id="T1",
        account="x",
        date=date(2024, 3, 1),
        ticker=SPX,
        quantity=1,
        adjusted_basis=100,
        option_details=o,
        cost_basis=100,
    )
    fmv_fn = _fmv_fn_factory({(SPX, 4000.0, "2027-06-19", "C", 2025): (Decimal("180"), "yahoo_close")})

    expected_key = position_key(account="x", ticker=SPX, option_details=o)

    def prior_mtm(pkey, year):
        if pkey == expected_key and year == 2024:
            return Decimal("150")
        return None

    out = mark_to_market(
        trades=[buy],
        lots=[lot],
        universe=UNIVERSE,
        tax_year=2025,
        fmv_fn=fmv_fn,
        prior_year_mtm_basis_fn=prior_mtm,
    )
    assert len(out) == 1
    assert out[0].basis_before == Decimal("150")
    assert out[0].unrealized_pnl == Decimal("30")
    assert out[0].long_term_portion == Decimal("18.00")
    assert out[0].short_term_portion == Decimal("12.00")


def test_mtm_at_loss_emits_negative_lt_and_st():
    o = _opt(4000.0, date(2026, 6, 19), "C")
    buy = Trade(
        account="x",
        date=date(2025, 3, 1),
        ticker=SPX,
        action="Buy",
        quantity=1,
        proceeds=None,
        cost_basis=200,
        option_details=o,
        is_section_1256=True,
    )
    lot = Lot(
        id="L1",
        trade_id="T1",
        account="x",
        date=date(2025, 3, 1),
        ticker=SPX,
        quantity=1,
        adjusted_basis=200,
        option_details=o,
        cost_basis=200,
    )
    fmv_fn = _fmv_fn_factory({(SPX, 4000.0, "2026-06-19", "C", 2025): (Decimal("50"), "black_scholes")})
    out = mark_to_market(
        trades=[buy],
        lots=[lot],
        universe=UNIVERSE,
        tax_year=2025,
        fmv_fn=fmv_fn,
        prior_year_mtm_basis_fn=_no_prior_mtm,
    )
    assert out[0].unrealized_pnl == Decimal("-150")
    assert out[0].long_term_portion == Decimal("-90.00")
    assert out[0].short_term_portion == Decimal("-60.00")
    assert out[0].fmv_source == "black_scholes"


def test_mtm_missing_fmv_emits_zero_with_missing_source():
    o = _opt(4000.0, date(2026, 6, 19), "C")
    buy = Trade(
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
    lot = Lot(
        id="L1",
        trade_id="T1",
        account="x",
        date=date(2025, 3, 1),
        ticker=SPX,
        quantity=1,
        adjusted_basis=100,
        option_details=o,
        cost_basis=100,
    )
    fmv_fn = _fmv_fn_factory({})
    out = mark_to_market(
        trades=[buy],
        lots=[lot],
        universe=UNIVERSE,
        tax_year=2025,
        fmv_fn=fmv_fn,
        prior_year_mtm_basis_fn=_no_prior_mtm,
    )
    assert len(out) == 1
    assert out[0].fmv_source == "missing"
    assert out[0].fmv == Decimal("0")
    assert out[0].unrealized_pnl == Decimal("-100")


def test_mtm_short_position_loss_when_fmv_rises():
    """Short call collected $50, year-end FMV $80 → unrealized LOSS of $30."""
    o = _opt(4000.0, date(2026, 6, 19), "C")
    sto = Trade(
        account="x",
        date=date(2025, 3, 1),
        ticker=SPX,
        action="Sell",
        quantity=1,
        proceeds=50,
        cost_basis=None,
        option_details=o,
        is_section_1256=True,
    )
    fmv_fn = _fmv_fn_factory({(SPX, 4000.0, "2026-06-19", "C", 2025): (Decimal("80"), "yahoo_close")})
    out = mark_to_market(
        trades=[sto],
        lots=[],
        universe=UNIVERSE,
        tax_year=2025,
        fmv_fn=fmv_fn,
        prior_year_mtm_basis_fn=_no_prior_mtm,
    )
    assert len(out) == 1
    m = out[0]
    assert m.unrealized_pnl == Decimal("-30")
    assert m.long_term_portion == Decimal("-18.00")
    assert m.short_term_portion == Decimal("-12.00")
