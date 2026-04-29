from datetime import date
from decimal import Decimal

from net_alpha.models.domain import Lot, OptionDetails, Trade
from net_alpha.section_1256.classifier import classify_closed_trades


def _spx_buy(d: date, premium: Decimal) -> Trade:
    return Trade(
        id=f"spx-buy-{d.isoformat()}",
        date=d,
        account="test/personal",
        ticker="SPX",
        action="Buy",
        quantity=1,
        proceeds=premium,
        cost_basis=premium,
        option_details=OptionDetails(strike=4500, expiry=date(2025, 12, 19), call_put="C"),
        is_section_1256=True,
    )


def _spx_sell(d: date, premium: Decimal) -> Trade:
    return Trade(
        id=f"spx-sell-{d.isoformat()}",
        date=d,
        account="test/personal",
        ticker="SPX",
        action="Sell",
        quantity=1,
        proceeds=premium,
        cost_basis=Decimal("0"),
        option_details=OptionDetails(strike=4500, expiry=date(2025, 12, 19), call_put="C"),
        is_section_1256=True,
    )


def _aapl_buy(d: date) -> Trade:
    return Trade(
        id=f"aapl-buy-{d.isoformat()}",
        date=d,
        account="test/personal",
        ticker="AAPL",
        action="Buy",
        quantity=10,
        proceeds=Decimal("1000"),
        cost_basis=Decimal("1000"),
        option_details=None,
        is_section_1256=False,
    )


def test_60_40_split_on_gain():
    buy = _spx_buy(date(2024, 1, 15), Decimal("100"))
    sell = _spx_sell(date(2024, 6, 15), Decimal("1100"))
    lots = [Lot.from_trade(buy)]
    result = classify_closed_trades([buy, sell], lots)
    assert len(result) == 1
    assert result[0].realized_pnl == Decimal("1000")
    assert result[0].long_term_portion == Decimal("600")
    assert result[0].short_term_portion == Decimal("400")
    assert result[0].underlying == "SPX"


def test_60_40_split_on_loss():
    buy = _spx_buy(date(2024, 1, 15), Decimal("1000"))
    sell = _spx_sell(date(2024, 6, 15), Decimal("0"))
    lots = [Lot.from_trade(buy)]
    result = classify_closed_trades([buy, sell], lots)
    assert result[0].realized_pnl == Decimal("-1000")
    assert result[0].long_term_portion == Decimal("-600")
    assert result[0].short_term_portion == Decimal("-400")


def test_holding_period_ignored_for_1256():
    """1-day-held SPX is still 60/40, not 100% short-term."""
    buy = _spx_buy(date(2024, 6, 15), Decimal("100"))
    sell = _spx_sell(date(2024, 6, 16), Decimal("200"))
    lots = [Lot.from_trade(buy)]
    result = classify_closed_trades([buy, sell], lots)
    assert result[0].long_term_portion == Decimal("60")
    assert result[0].short_term_portion == Decimal("40")


def test_non_1256_trades_skipped():
    buy = _aapl_buy(date(2024, 1, 15))
    sell = Trade(
        id="aapl-sell",
        date=date(2024, 6, 15),
        account="test/personal",
        ticker="AAPL",
        action="Sell",
        quantity=10,
        proceeds=Decimal("1100"),
        cost_basis=Decimal("0"),
        option_details=None,
        is_section_1256=False,
    )
    lots = [Lot.from_trade(buy)]
    assert classify_closed_trades([buy, sell], lots) == []


def test_open_position_not_classified():
    buy = _spx_buy(date(2024, 1, 15), Decimal("100"))
    lots = [Lot.from_trade(buy)]
    assert classify_closed_trades([buy], lots) == []


def test_buy_only_no_sell_returns_empty():
    assert classify_closed_trades([], []) == []
