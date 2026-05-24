from datetime import date

from net_alpha.engine.detector import detect_wash_sales
from net_alpha.models.domain import OptionDetails
from tests.conftest import LossSaleFactory, TradeFactory


def test_simple_equity_wash_sale():
    """Sell TSLA at loss, rebuy within 30 days → Confirmed."""
    sell = LossSaleFactory(
        account="Schwab",
        date=date(2024, 10, 15),
        ticker="TSLA",
        quantity=10.0,
        proceeds=2400.0,
        cost_basis=3600.0,
    )
    buy = TradeFactory(
        account="Robinhood",
        date=date(2024, 11, 3),
        ticker="TSLA",
        action="Buy",
        quantity=15.0,
        cost_basis=3750.0,
    )
    result = detect_wash_sales([sell, buy], {})

    assert len(result.violations) == 1
    v = result.violations[0]
    assert v.loss_trade_id == sell.id
    assert v.replacement_trade_id == buy.id
    assert v.confidence == "Confirmed"
    assert v.disallowed_loss == 1200.0
    assert v.matched_quantity == 10.0


def test_no_wash_sale_outside_window():
    """Buy 31 days after sell → no wash sale."""
    sell = LossSaleFactory(
        date=date(2024, 10, 15),
        ticker="TSLA",
        quantity=10.0,
        proceeds=2400.0,
        cost_basis=3600.0,
    )
    buy = TradeFactory(
        date=date(2024, 11, 15),  # Day 31
        ticker="TSLA",
        action="Buy",
        quantity=10.0,
    )
    result = detect_wash_sales([sell, buy], {})
    assert len(result.violations) == 0


def test_no_wash_sale_on_gain():
    """Sell at a gain → no wash sale regardless of repurchase."""
    sell = TradeFactory(
        action="Sell",
        date=date(2024, 10, 15),
        ticker="TSLA",
        quantity=10.0,
        proceeds=5000.0,
        cost_basis=3600.0,
    )
    buy = TradeFactory(
        date=date(2024, 10, 20),
        ticker="TSLA",
        action="Buy",
        quantity=10.0,
    )
    result = detect_wash_sales([sell, buy], {})
    assert len(result.violations) == 0


def test_look_back_window():
    """Buy 15 days BEFORE loss sale → still a wash sale."""
    buy = TradeFactory(
        date=date(2024, 10, 1),
        ticker="TSLA",
        action="Buy",
        quantity=10.0,
        cost_basis=2500.0,
    )
    sell = LossSaleFactory(
        date=date(2024, 10, 15),
        ticker="TSLA",
        quantity=10.0,
        proceeds=2000.0,
        cost_basis=3000.0,
    )
    result = detect_wash_sales([sell, buy], {})
    assert len(result.violations) == 1
    assert result.violations[0].confidence == "Confirmed"


def test_fifo_allocation_earliest_buy_first():
    """Multiple buys in window — earliest buy absorbs disallowed loss first."""
    sell = LossSaleFactory(
        date=date(2024, 10, 15),
        ticker="TSLA",
        quantity=10.0,
        proceeds=2000.0,
        cost_basis=3000.0,
    )
    buy1 = TradeFactory(
        date=date(2024, 10, 20),
        ticker="TSLA",
        action="Buy",
        quantity=5.0,
        cost_basis=1200.0,
    )
    buy2 = TradeFactory(
        date=date(2024, 10, 25),
        ticker="TSLA",
        action="Buy",
        quantity=8.0,
        cost_basis=2000.0,
    )
    result = detect_wash_sales([sell, buy1, buy2], {})

    assert len(result.violations) == 2
    # First violation: 5 shares allocated to buy1 (earlier)
    v1 = result.violations[0]
    assert v1.replacement_trade_id == buy1.id
    assert v1.matched_quantity == 5.0
    assert v1.disallowed_loss == 500.0  # 5/10 * 1000

    # Second violation: 5 shares allocated to buy2 (later)
    v2 = result.violations[1]
    assert v2.replacement_trade_id == buy2.id
    assert v2.matched_quantity == 5.0
    assert v2.disallowed_loss == 500.0


def test_partial_wash_sale_fewer_shares_bought():
    """Bought fewer shares than sold — partial wash sale."""
    sell = LossSaleFactory(
        date=date(2024, 10, 15),
        ticker="TSLA",
        quantity=100.0,
        proceeds=20000.0,
        cost_basis=30000.0,
    )
    buy = TradeFactory(
        date=date(2024, 10, 20),
        ticker="TSLA",
        action="Buy",
        quantity=40.0,
        cost_basis=9000.0,
    )
    result = detect_wash_sales([sell, buy], {})

    assert len(result.violations) == 1
    v = result.violations[0]
    assert v.matched_quantity == 40.0
    assert v.disallowed_loss == 4000.0  # 40/100 * 10000


def test_adjusted_basis_updated():
    """Disallowed loss rolls into replacement lot's adjusted basis."""
    sell = LossSaleFactory(
        date=date(2024, 10, 15),
        ticker="TSLA",
        quantity=10.0,
        proceeds=2000.0,
        cost_basis=3200.0,
    )
    buy = TradeFactory(
        date=date(2024, 10, 20),
        ticker="TSLA",
        action="Buy",
        quantity=10.0,
        cost_basis=2500.0,
    )
    result = detect_wash_sales([sell, buy], {})

    # Find the lot for the buy
    lot = next(lot_ for lot_ in result.lots if lot_.trade_id == buy.id)
    assert lot.cost_basis == 2500.0
    assert lot.adjusted_basis == 2500.0 + 1200.0  # 3700.0


def test_same_day_buy_and_sell():
    """Same-day buy and sell — always a wash sale."""
    sell = LossSaleFactory(
        date=date(2024, 10, 15),
        ticker="TSLA",
        quantity=10.0,
        proceeds=2000.0,
        cost_basis=3000.0,
    )
    buy = TradeFactory(
        date=date(2024, 10, 15),
        ticker="TSLA",
        action="Buy",
        quantity=10.0,
        cost_basis=2100.0,
    )
    result = detect_wash_sales([sell, buy], {})
    assert len(result.violations) == 1
    assert result.violations[0].confidence == "Confirmed"


def test_cross_account_wash_sale():
    """Loss on Schwab, rebuy on Robinhood → detected."""
    sell = LossSaleFactory(
        account="Schwab",
        date=date(2024, 10, 15),
        ticker="NVDA",
        quantity=20.0,
        proceeds=2000.0,
        cost_basis=3000.0,
    )
    buy = TradeFactory(
        account="Robinhood",
        date=date(2024, 10, 20),
        ticker="NVDA",
        action="Buy",
        quantity=20.0,
        cost_basis=2200.0,
    )
    result = detect_wash_sales([sell, buy], {})

    assert len(result.violations) == 1
    v = result.violations[0]
    assert v.confidence == "Confirmed"
    assert v.disallowed_loss == 1000.0


def test_cross_year_wash_sale():
    """Dec 20 loss sale, Jan 5 buy → wash sale detected."""
    sell = LossSaleFactory(
        date=date(2024, 12, 20),
        ticker="AAPL",
        quantity=50.0,
        proceeds=5000.0,
        cost_basis=7500.0,
    )
    buy = TradeFactory(
        date=date(2025, 1, 5),
        ticker="AAPL",
        action="Buy",
        quantity=50.0,
        cost_basis=5500.0,
    )
    result = detect_wash_sales([sell, buy], {})

    assert len(result.violations) == 1
    assert result.violations[0].disallowed_loss == 2500.0


def test_basis_unknown_excluded_as_loss_sale():
    """Trades with basis_unknown cannot be loss sale candidates."""
    sell = TradeFactory(
        action="Sell",
        date=date(2024, 10, 15),
        ticker="TSLA",
        quantity=10.0,
        proceeds=2000.0,
        basis_unknown=True,
    )
    buy = TradeFactory(
        date=date(2024, 10, 20),
        ticker="TSLA",
        action="Buy",
        quantity=10.0,
        cost_basis=2500.0,
    )
    result = detect_wash_sales([sell, buy], {})
    assert len(result.violations) == 0


def test_basis_unknown_can_be_replacement_buy():
    """basis_unknown buy CAN trigger a wash sale on a known-basis loss sale."""
    sell = LossSaleFactory(
        date=date(2024, 10, 15),
        ticker="TSLA",
        quantity=10.0,
        proceeds=2000.0,
        cost_basis=3000.0,
    )
    buy = TradeFactory(
        date=date(2024, 10, 20),
        ticker="TSLA",
        action="Buy",
        quantity=10.0,
        basis_unknown=True,
        cost_basis=None,
    )
    result = detect_wash_sales([sell, buy], {})

    assert len(result.violations) == 1
    assert result.violations[0].disallowed_loss == 1000.0
    assert result.basis_unknown_count == 1


def test_basis_unknown_count():
    """Detection result counts basis_unknown trades."""
    trades = [
        TradeFactory(basis_unknown=True),
        TradeFactory(basis_unknown=True),
        TradeFactory(basis_unknown=False),
    ]
    result = detect_wash_sales(trades, {})
    assert result.basis_unknown_count == 2


def test_multiple_loss_sales_share_same_buy_lot():
    """Two loss sales match the same buy — lot quantity split between them."""
    sell1 = LossSaleFactory(
        date=date(2024, 10, 10),
        ticker="TSLA",
        quantity=5.0,
        proceeds=1000.0,
        cost_basis=1500.0,
    )
    sell2 = LossSaleFactory(
        date=date(2024, 10, 15),
        ticker="TSLA",
        quantity=5.0,
        proceeds=1000.0,
        cost_basis=1500.0,
    )
    buy = TradeFactory(
        date=date(2024, 10, 20),
        ticker="TSLA",
        action="Buy",
        quantity=8.0,
        cost_basis=2000.0,
    )
    result = detect_wash_sales([sell1, sell2, buy], {})

    assert len(result.violations) == 2
    # sell1 consumes 5 of buy's 8 shares
    assert result.violations[0].matched_quantity == 5.0
    assert result.violations[0].disallowed_loss == 500.0
    # sell2 consumes remaining 3 of buy's 8 shares
    assert result.violations[1].matched_quantity == 3.0
    assert result.violations[1].disallowed_loss == 300.0


def test_no_trades_empty_result():
    result = detect_wash_sales([], {})
    assert result.violations == []
    assert result.lots == []
    assert result.basis_unknown_count == 0


ETF_PAIRS = {
    "sp500": ["SPY", "VOO", "IVV", "SPLG"],
    "nasdaq100": ["QQQ", "QQQM"],
}


def test_option_wash_sale_same_option():
    """Sold option at loss, rebought identical option → Confirmed."""
    sell = LossSaleFactory(
        date=date(2024, 10, 15),
        ticker="TSLA",
        quantity=1.0,
        proceeds=200.0,
        cost_basis=500.0,
        option_details=OptionDetails(strike=250.0, expiry=date(2024, 12, 20), call_put="C"),
    )
    buy = TradeFactory(
        date=date(2024, 10, 20),
        ticker="TSLA",
        action="Buy",
        quantity=1.0,
        cost_basis=450.0,
        option_details=OptionDetails(strike=250.0, expiry=date(2024, 12, 20), call_put="C"),
    )
    result = detect_wash_sales([sell, buy], {})

    assert len(result.violations) == 1
    assert result.violations[0].confidence == "Confirmed"
    assert result.violations[0].disallowed_loss == 300.0


def test_option_wash_sale_different_strike():
    """Sold option at loss, bought different strike → Probable."""
    sell = LossSaleFactory(
        date=date(2024, 10, 15),
        ticker="TSLA",
        quantity=1.0,
        proceeds=200.0,
        cost_basis=500.0,
        option_details=OptionDetails(strike=250.0, expiry=date(2024, 12, 20), call_put="C"),
    )
    buy = TradeFactory(
        date=date(2024, 10, 20),
        ticker="TSLA",
        action="Buy",
        quantity=1.0,
        cost_basis=600.0,
        option_details=OptionDetails(strike=300.0, expiry=date(2024, 12, 20), call_put="C"),
    )
    result = detect_wash_sales([sell, buy], {})

    assert len(result.violations) == 1
    assert result.violations[0].confidence == "Probable"


def test_stock_loss_call_purchase():
    """Sold stock at loss, bought call → Probable."""
    sell = LossSaleFactory(
        date=date(2024, 10, 15),
        ticker="TSLA",
        quantity=10.0,
        proceeds=2000.0,
        cost_basis=3000.0,
    )
    buy = TradeFactory(
        date=date(2024, 10, 20),
        ticker="TSLA",
        action="Buy",
        quantity=1.0,
        cost_basis=500.0,
        option_details=OptionDetails(strike=250.0, expiry=date(2024, 12, 20), call_put="C"),
    )
    result = detect_wash_sales([sell, buy], {})

    assert len(result.violations) == 1
    assert result.violations[0].confidence == "Probable"


def test_stock_loss_sold_put_unclear():
    """Sold stock at loss, sold put → Unclear."""
    sell = LossSaleFactory(
        date=date(2024, 10, 15),
        ticker="TSLA",
        quantity=10.0,
        proceeds=2000.0,
        cost_basis=3000.0,
    )
    sold_put = TradeFactory(
        date=date(2024, 10, 20),
        ticker="TSLA",
        action="Sell",
        quantity=1.0,
        proceeds=300.0,
        cost_basis=None,
        option_details=OptionDetails(strike=200.0, expiry=date(2024, 12, 20), call_put="P"),
    )
    result = detect_wash_sales([sell, sold_put], {})

    assert len(result.violations) == 1
    assert result.violations[0].confidence == "Unclear"


def test_etf_substantially_identical_wash_sale():
    """Sold SPY at loss, bought VOO → Unclear."""
    sell = LossSaleFactory(
        date=date(2024, 10, 15),
        ticker="SPY",
        quantity=10.0,
        proceeds=4000.0,
        cost_basis=5000.0,
    )
    buy = TradeFactory(
        date=date(2024, 10, 20),
        ticker="VOO",
        action="Buy",
        quantity=10.0,
        cost_basis=4200.0,
    )
    result = detect_wash_sales([sell, buy], ETF_PAIRS)

    assert len(result.violations) == 1
    assert result.violations[0].confidence == "Unclear"
    assert result.violations[0].disallowed_loss == 1000.0


def test_etf_no_match_different_group():
    """SPY loss, QQQ buy → no wash sale (different index groups)."""
    sell = LossSaleFactory(
        date=date(2024, 10, 15),
        ticker="SPY",
        quantity=10.0,
        proceeds=4000.0,
        cost_basis=5000.0,
    )
    buy = TradeFactory(
        date=date(2024, 10, 20),
        ticker="QQQ",
        action="Buy",
        quantity=10.0,
        cost_basis=3000.0,
    )
    result = detect_wash_sales([sell, buy], ETF_PAIRS)
    assert len(result.violations) == 0


def test_buy_to_close_does_not_seed_long_lot():
    """A `Buy to Close` (basis_source='option_short_close') closes a short
    option position — it must NOT create a long lot, otherwise the holdings
    table would show a phantom +1 contract long position after a round-trip
    sold-put close.
    """
    btc = TradeFactory(
        date=date(2026, 1, 9),
        ticker="UUUU",
        action="Buy",
        quantity=1.0,
        cost_basis=140.66,
        basis_source="option_short_close",
        option_details=OptionDetails(strike=20.0, expiry=date(2026, 1, 16), call_put="P"),
    )
    result = detect_wash_sales([btc], {})
    assert result.lots == []


def test_buy_to_open_still_seeds_long_lot():
    """Sanity: regular Buy / BTO (no `option_short_close` marker) still
    creates a lot — only short-close BTCs are excluded.
    """
    bto = TradeFactory(
        date=date(2026, 1, 9),
        ticker="TSLA",
        action="Buy",
        quantity=1.0,
        cost_basis=400.0,
        option_details=OptionDetails(strike=400.0, expiry=date(2026, 6, 18), call_put="C"),
    )
    result = detect_wash_sales([bto], {})
    assert len(result.lots) == 1
    assert result.lots[0].ticker == "TSLA"


def test_multi_buy_partial_disallowed_loss_sums_to_loss_with_no_drift():
    """Audit #40: with three qty-1 buys against a qty-3 loss sale of $1.00,
    per-unit float math (1.00/3 = 0.3333… rounded to $0.33 per match) would
    leave a one-cent residual. Decimal-cent apportionment must yield a sum
    EXACTLY equal to the loss-sale's total disallowed loss.
    """
    sell = LossSaleFactory(
        date=date(2024, 10, 15),
        ticker="TSLA",
        quantity=3.0,
        proceeds=2.0,
        cost_basis=3.0,  # $1.00 total loss
    )
    buy_a = TradeFactory(id="buy-a", date=date(2024, 10, 20), ticker="TSLA", action="Buy", quantity=1.0, cost_basis=1.0)
    buy_b = TradeFactory(id="buy-b", date=date(2024, 10, 21), ticker="TSLA", action="Buy", quantity=1.0, cost_basis=1.0)
    buy_c = TradeFactory(id="buy-c", date=date(2024, 10, 22), ticker="TSLA", action="Buy", quantity=1.0, cost_basis=1.0)
    result = detect_wash_sales([sell, buy_a, buy_b, buy_c], {})
    assert len(result.violations) == 3
    # Sum of disallowed across the three matches must equal the loss-sale's
    # full $1.00, with no penny drift.
    total = sum(v.disallowed_loss for v in result.violations)
    assert round(total, 2) == 1.00, f"disallowed losses sum to {total!r}, expected 1.00"
    # Each per-match disallowed is quantized to cents (no sub-cent values).
    for v in result.violations:
        assert round(v.disallowed_loss * 100) == v.disallowed_loss * 100, (
            f"disallowed_loss {v.disallowed_loss} is not whole cents"
        )


def test_multi_buy_repeated_recompute_has_no_basis_churn():
    """Audit #40: with Decimal-cent apportionment, the recompute loop's
    _rebuild_adjusted_basis_from_violations must not see sub-cent drift between
    iterations — five back-to-back recomputes must leave adjusted_basis stable.
    """
    from pathlib import Path

    from sqlmodel import SQLModel, create_engine

    from net_alpha.db.repository import Repository
    from net_alpha.engine.recompute import recompute_all_violations

    tmp = Path("/tmp/net_alpha_audit40_churn.db")
    if tmp.exists():
        tmp.unlink()
    engine = create_engine(f"sqlite:///{tmp}")
    SQLModel.metadata.create_all(engine)
    repo = Repository(engine)

    from datetime import datetime

    from net_alpha.models.domain import ImportRecord, Trade

    account = repo.get_or_create_account("Schwab", "Taxable")
    trades = [
        Trade(
            account="Schwab/Taxable",
            date=date(2024, 10, 15),
            ticker="TSLA",
            action="Sell",
            quantity=3.0,
            proceeds=2.0,
            cost_basis=3.0,
        ),
        Trade(
            account="Schwab/Taxable",
            date=date(2024, 10, 20),
            ticker="TSLA",
            action="Buy",
            quantity=1.0,
            cost_basis=1.0,
        ),
        Trade(
            account="Schwab/Taxable",
            date=date(2024, 10, 21),
            ticker="TSLA",
            action="Buy",
            quantity=1.0,
            cost_basis=1.0,
        ),
        Trade(
            account="Schwab/Taxable",
            date=date(2024, 10, 22),
            ticker="TSLA",
            action="Buy",
            quantity=1.0,
            cost_basis=1.0,
        ),
    ]
    record = ImportRecord(
        account_id=account.id,
        csv_filename="audit40.csv",
        csv_sha256="sha-audit40",
        imported_at=datetime.now(),
        trade_count=len(trades),
    )
    repo.add_import(account, record, trades)

    recompute_all_violations(repo, etf_pairs={})
    snapshot_1 = sorted((lot.trade_id, round(lot.adjusted_basis, 6)) for lot in repo.all_lots())
    for _ in range(5):
        recompute_all_violations(repo, etf_pairs={})
    snapshot_2 = sorted((lot.trade_id, round(lot.adjusted_basis, 6)) for lot in repo.all_lots())
    assert snapshot_1 == snapshot_2, f"adjusted_basis drifted across recomputes: {snapshot_1} -> {snapshot_2}"

    tmp.unlink()
