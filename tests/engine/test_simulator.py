from datetime import date
from decimal import Decimal

from net_alpha.engine.simulator import simulate_sell
from net_alpha.models.domain import Account, Lot, OptionDetails, Trade


def _lot(account: str, date_, ticker, qty, basis):
    return Lot(
        trade_id="x", account=account, date=date_, ticker=ticker, quantity=qty, cost_basis=basis, adjusted_basis=basis
    )


def _option_lot(account: str, date_, ticker, qty, basis, strike):
    return Lot(
        trade_id="x",
        account=account,
        date=date_,
        ticker=ticker,
        quantity=qty,
        cost_basis=basis,
        adjusted_basis=basis,
        option_details=OptionDetails(strike=strike, expiry=date(2026, 6, 5), call_put="P"),
    )


def test_stock_sale_does_not_consume_option_lots_of_same_ticker():
    # A stock sale must only draw from equity lots. Option lots share the
    # underlying ticker but carry per-contract premium basis (e.g. $365), so
    # consuming them as if they were shares fabricates absurd realized P&L.
    # The option lot is dated between the equity lots so a naive FIFO walk
    # would consume it after the first equity lot is exhausted.
    p = Account(id=1, broker="schwab", label="st")
    lots = [
        _lot("schwab/st", date(2025, 6, 23), "HIMS", 3, 131.10),  # $43.70/sh equity
        _option_lot("schwab/st", date(2025, 7, 2), "HIMS", 1, 365.66, strike=100.0),  # option premium
        _lot("schwab/st", date(2025, 7, 17), "HIMS", 3, 150.0),  # $50/sh equity
    ]
    options = simulate_sell("HIMS", Decimal("5"), Decimal("23.75"), accounts=[p], existing_lots=lots, recent_trades=[])
    opt = options[0]
    # Equity-only FIFO: 3*(23.75-43.70) + 2*(23.75-50) = -59.85 + -52.50 = -112.35.
    # The option lot's $365.66 premium must never enter the share consumption.
    assert opt.realized_pnl == Decimal("-112.35")
    assert all(c.basis_per_share < Decimal("100") for c in opt.lots_consumed_fifo)


def test_returns_one_option_per_holding_account():
    p = Account(id=1, broker="schwab", label="personal")
    r = Account(id=2, broker="schwab", label="roth")
    lots = [
        _lot("schwab/personal", date(2024, 8, 15), "TSLA", 10, 2000),
        _lot("schwab/roth", date(2024, 9, 22), "TSLA", 10, 1500),
    ]
    options = simulate_sell("TSLA", Decimal("5"), Decimal("180"), accounts=[p, r], existing_lots=lots, recent_trades=[])
    assert {o.account.label for o in options} == {"personal", "roth"}


def test_personal_option_realized_pnl_uses_personal_lots_only():
    p = Account(id=1, broker="schwab", label="personal")
    r = Account(id=2, broker="schwab", label="roth")
    lots = [
        _lot("schwab/personal", date(2024, 8, 15), "TSLA", 10, 2000),  # $200/share basis
        _lot("schwab/roth", date(2024, 9, 22), "TSLA", 10, 1500),  # $150/share basis
    ]
    options = simulate_sell("TSLA", Decimal("5"), Decimal("180"), accounts=[p, r], existing_lots=lots, recent_trades=[])
    by_label = {o.account.label: o for o in options}
    # Personal: 5 * (180 - 200) = -100
    assert by_label["personal"].realized_pnl == Decimal("-100")
    # Roth: 5 * (180 - 150) = 150
    assert by_label["roth"].realized_pnl == Decimal("150")


def test_loss_with_recent_buy_on_other_account_flags_wash_sale():
    p = Account(id=1, broker="schwab", label="personal")
    r = Account(id=2, broker="schwab", label="roth")
    lots = [_lot("schwab/personal", date(2024, 8, 15), "TSLA", 10, 2000)]
    recent_buy = Trade(
        account="schwab/roth",
        date=date(2024, 9, 22),
        ticker="TSLA",
        action="Buy",
        quantity=10,
        cost_basis=1500.0,
    )
    options = simulate_sell(
        "TSLA",
        Decimal("5"),
        Decimal("180"),
        accounts=[p, r],
        existing_lots=lots,
        recent_trades=[recent_buy],
        today=date(2024, 9, 25),
    )
    p_opt = next(o for o in options if o.account.label == "personal")
    assert p_opt.would_trigger_wash_sale is True
    assert p_opt.confidence == "Confirmed"


def test_insufficient_shares_marks_option_but_still_returns_it():
    p = Account(id=1, broker="schwab", label="personal")
    lots = [_lot("schwab/personal", date(2024, 8, 15), "TSLA", 3, 600)]
    options = simulate_sell("TSLA", Decimal("10"), Decimal("180"), accounts=[p], existing_lots=lots, recent_trades=[])
    assert len(options) == 1
    assert options[0].insufficient_shares is True
    assert options[0].available_shares == Decimal("3")


def test_account_with_no_holdings_is_not_returned():
    p = Account(id=1, broker="schwab", label="personal")
    r = Account(id=2, broker="schwab", label="roth")
    lots = [_lot("schwab/personal", date(2024, 8, 15), "TSLA", 10, 2000)]
    options = simulate_sell("TSLA", Decimal("5"), Decimal("180"), accounts=[p, r], existing_lots=lots, recent_trades=[])
    assert {o.account.label for o in options} == {"personal"}


def test_gain_skips_wash_sale_check():
    p = Account(id=1, broker="schwab", label="personal")
    lots = [_lot("schwab/personal", date(2024, 8, 15), "TSLA", 10, 1500)]  # basis below price
    options = simulate_sell("TSLA", Decimal("5"), Decimal("180"), accounts=[p], existing_lots=lots, recent_trades=[])
    assert options[0].would_trigger_wash_sale is False
    assert options[0].confidence == "N/A"


def test_lookforward_block_until_set_when_loss():
    p = Account(id=1, broker="schwab", label="personal")
    lots = [_lot("schwab/personal", date(2024, 8, 15), "TSLA", 10, 2000)]
    options = simulate_sell(
        "TSLA",
        Decimal("5"),
        Decimal("180"),
        accounts=[p],
        existing_lots=lots,
        recent_trades=[],
        today=date(2024, 10, 1),
    )
    from datetime import timedelta

    assert options[0].lookforward_block_until == date(2024, 10, 1) + timedelta(days=30)
