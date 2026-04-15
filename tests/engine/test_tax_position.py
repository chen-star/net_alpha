from datetime import date

from net_alpha.engine.tax_position import (
    _allocate_lots,
    compute_tax_position,
    identify_open_lots,
    recommend_lot_method,
    select_lots,
)
from net_alpha.models.domain import LotRecommendation, LotSelection, OptionDetails, TaxPosition
from tests.conftest import LossSaleFactory, OpenLotFactory, TradeFactory


class TestAllocateLots:
    def test_single_buy_single_sell_fully_consumed(self):
        """Buy 10, sell 10 → no open lots, one realized pair."""
        buy = TradeFactory(
            account="Schwab",
            date=date(2025, 1, 15),
            ticker="AAPL",
            action="Buy",
            quantity=10.0,
            cost_basis=1500.0,
        )
        sell = TradeFactory(
            account="Schwab",
            date=date(2025, 7, 20),
            ticker="AAPL",
            action="Sell",
            quantity=10.0,
            proceeds=1800.0,
            cost_basis=1500.0,
        )
        result = _allocate_lots([buy, sell], as_of=date(2025, 12, 1))

        assert len(result.realized_pairs) == 1
        assert len(result.open_lots) == 0
        rp = result.realized_pairs[0]
        assert rp.sell_trade_id == sell.id
        assert rp.quantity == 10.0
        assert rp.proceeds == 1800.0
        assert rp.basis == 1500.0
        assert rp.is_long_term is False  # Jan 15 to Jul 20 = 186 days

    def test_single_buy_no_sell_all_open(self):
        """Buy 50 shares, no sell → 50 shares open."""
        buy = TradeFactory(
            account="Schwab",
            date=date(2025, 6, 1),
            ticker="AAPL",
            action="Buy",
            quantity=50.0,
            cost_basis=7250.0,
        )
        result = _allocate_lots([buy], as_of=date(2026, 4, 14))

        assert len(result.realized_pairs) == 0
        assert len(result.open_lots) == 1
        lot = result.open_lots[0]
        assert lot.ticker == "AAPL"
        assert lot.account == "Schwab"
        assert lot.quantity == 50.0
        assert lot.adjusted_basis_per_share == 145.0  # 7250 / 50
        assert lot.purchase_date == date(2025, 6, 1)
        # Jun 1 2025 to Apr 14 2026 = 317 days
        assert lot.days_held == 317
        # 366 - 317 = 49 days to long-term
        assert lot.days_to_long_term == 49

    def test_partial_sell_leaves_open_lot(self):
        """Buy 100, sell 60 → 40 open with correct remaining basis."""
        buy = TradeFactory(
            account="Schwab",
            date=date(2025, 1, 10),
            ticker="AAPL",
            action="Buy",
            quantity=100.0,
            cost_basis=15000.0,
        )
        sell = TradeFactory(
            account="Schwab",
            date=date(2025, 6, 15),
            ticker="AAPL",
            action="Sell",
            quantity=60.0,
            proceeds=10200.0,
            cost_basis=9000.0,
        )
        result = _allocate_lots([buy, sell], as_of=date(2025, 12, 1))

        assert len(result.realized_pairs) == 1
        rp = result.realized_pairs[0]
        assert rp.quantity == 60.0
        assert rp.basis == 9000.0  # 60 * 150

        assert len(result.open_lots) == 1
        lot = result.open_lots[0]
        assert lot.quantity == 40.0
        assert lot.adjusted_basis_per_share == 150.0  # 6000 / 40

    def test_fifo_order_multiple_buys(self):
        """Two buys, one sell — FIFO consumes earliest first."""
        buy1 = TradeFactory(
            account="Schwab", date=date(2025, 1, 10), ticker="AAPL",
            action="Buy", quantity=30.0, cost_basis=4500.0,
        )
        buy2 = TradeFactory(
            account="Schwab", date=date(2025, 3, 1), ticker="AAPL",
            action="Buy", quantity=40.0, cost_basis=6400.0,
        )
        sell = TradeFactory(
            account="Schwab", date=date(2025, 6, 15), ticker="AAPL",
            action="Sell", quantity=50.0, proceeds=8500.0, cost_basis=7700.0,
        )
        result = _allocate_lots([buy1, buy2, sell], as_of=date(2025, 12, 1))

        assert len(result.realized_pairs) == 2
        rp1 = result.realized_pairs[0]
        assert rp1.quantity == 30.0
        assert rp1.basis == 4500.0
        assert rp1.buy_lot_date == date(2025, 1, 10)
        rp2 = result.realized_pairs[1]
        assert rp2.quantity == 20.0
        assert rp2.basis == 3200.0  # 20 * 160
        assert rp2.buy_lot_date == date(2025, 3, 1)

        assert len(result.open_lots) == 1
        lot = result.open_lots[0]
        assert lot.quantity == 20.0
        assert lot.adjusted_basis_per_share == 160.0

    def test_per_account_isolation(self):
        """Sell on Schwab does NOT consume Robinhood lots."""
        schwab_buy = TradeFactory(
            account="Schwab", date=date(2025, 1, 10), ticker="AAPL",
            action="Buy", quantity=30.0, cost_basis=4500.0,
        )
        robin_buy = TradeFactory(
            account="Robinhood", date=date(2025, 2, 1), ticker="AAPL",
            action="Buy", quantity=50.0, cost_basis=7500.0,
        )
        schwab_sell = TradeFactory(
            account="Schwab", date=date(2025, 6, 15), ticker="AAPL",
            action="Sell", quantity=30.0, proceeds=5100.0, cost_basis=4500.0,
        )
        result = _allocate_lots(
            [schwab_buy, robin_buy, schwab_sell], as_of=date(2025, 12, 1)
        )

        assert len(result.realized_pairs) == 1
        rp = result.realized_pairs[0]
        assert rp.buy_lot_account == "Schwab"

        assert len(result.open_lots) == 1
        lot = result.open_lots[0]
        assert lot.account == "Robinhood"
        assert lot.quantity == 50.0

    def test_same_date_buys_ordered_by_id(self):
        """Two buys on same date — ordered by id for determinism."""
        buy_a = TradeFactory(
            id="aaa",
            account="Schwab", date=date(2025, 1, 15), ticker="AAPL",
            action="Buy", quantity=30.0, cost_basis=4500.0,
        )
        buy_b = TradeFactory(
            id="bbb",
            account="Schwab", date=date(2025, 1, 15), ticker="AAPL",
            action="Buy", quantity=40.0, cost_basis=6000.0,
        )
        sell = TradeFactory(
            account="Schwab", date=date(2025, 6, 15), ticker="AAPL",
            action="Sell", quantity=40.0, proceeds=6800.0, cost_basis=6100.0,
        )
        result = _allocate_lots([buy_a, buy_b, sell], as_of=date(2025, 12, 1))

        assert len(result.realized_pairs) == 2
        assert result.realized_pairs[0].buy_lot_date == date(2025, 1, 15)
        assert result.realized_pairs[0].quantity == 30.0
        assert result.realized_pairs[1].quantity == 10.0

        assert len(result.open_lots) == 1
        assert result.open_lots[0].quantity == 30.0

    def test_basis_unknown_buy_lot(self):
        """basis_unknown buy → open lot has basis_unknown=True."""
        buy = TradeFactory(
            account="Schwab", date=date(2025, 1, 10), ticker="AAPL",
            action="Buy", quantity=10.0, cost_basis=None, basis_unknown=True,
        )
        result = _allocate_lots([buy], as_of=date(2025, 12, 1))

        assert len(result.open_lots) == 1
        assert result.open_lots[0].basis_unknown is True
        assert result.open_lots[0].adjusted_basis_per_share == 0.0

    def test_basis_unknown_realized_pair(self):
        """Sell consuming basis_unknown buy → realized pair marked."""
        buy = TradeFactory(
            account="Schwab", date=date(2025, 1, 10), ticker="AAPL",
            action="Buy", quantity=10.0, cost_basis=None, basis_unknown=True,
        )
        sell = TradeFactory(
            account="Schwab", date=date(2025, 6, 15), ticker="AAPL",
            action="Sell", quantity=10.0, proceeds=1800.0, cost_basis=None,
        )
        result = _allocate_lots([buy, sell], as_of=date(2025, 12, 1))

        assert len(result.realized_pairs) == 1
        assert result.realized_pairs[0].basis_unknown is True
        assert result.realized_pairs[0].basis == 0.0

    def test_option_trades_excluded_from_open_lots(self):
        """Option buys do not appear as open lots."""
        buy = TradeFactory(
            account="Schwab", date=date(2025, 1, 10), ticker="AAPL",
            action="Buy", quantity=1.0, cost_basis=500.0,
            option_details=OptionDetails(strike=150.0, expiry=date(2025, 6, 20), call_put="C"),
        )
        result = _allocate_lots([buy], as_of=date(2025, 12, 1))

        assert len(result.open_lots) == 0

    def test_holding_period_exactly_365_days(self):
        """Held exactly 365 days → short-term (> 365 for long-term)."""
        buy = TradeFactory(
            account="Schwab", date=date(2025, 1, 1), ticker="AAPL",
            action="Buy", quantity=10.0, cost_basis=1500.0,
        )
        sell = TradeFactory(
            account="Schwab", date=date(2026, 1, 1), ticker="AAPL",
            action="Sell", quantity=10.0, proceeds=1800.0, cost_basis=1500.0,
        )
        result = _allocate_lots([buy, sell], as_of=date(2026, 6, 1))

        rp = result.realized_pairs[0]
        assert rp.is_long_term is False  # exactly 365 = short-term

    def test_holding_period_366_days(self):
        """Held 366 days → long-term."""
        buy = TradeFactory(
            account="Schwab", date=date(2025, 1, 1), ticker="AAPL",
            action="Buy", quantity=10.0, cost_basis=1500.0,
        )
        sell = TradeFactory(
            account="Schwab", date=date(2026, 1, 2), ticker="AAPL",
            action="Sell", quantity=10.0, proceeds=1800.0, cost_basis=1500.0,
        )
        result = _allocate_lots([buy, sell], as_of=date(2026, 6, 1))

        rp = result.realized_pairs[0]
        assert rp.is_long_term is True

    def test_days_to_long_term_computation(self):
        """Open lot correctly computes days_to_long_term."""
        buy = TradeFactory(
            account="Schwab", date=date(2025, 6, 1), ticker="AAPL",
            action="Buy", quantity=50.0, cost_basis=7250.0,
        )
        # as_of = 2026-04-14 → 317 days held → 366-317 = 49 days to LT
        result = _allocate_lots([buy], as_of=date(2026, 4, 14))

        lot = result.open_lots[0]
        assert lot.days_held == 317
        assert lot.days_to_long_term == 49

    def test_already_long_term_open_lot(self):
        """Open lot held > 365 days → days_to_long_term = 0."""
        buy = TradeFactory(
            account="Schwab", date=date(2025, 1, 1), ticker="AAPL",
            action="Buy", quantity=20.0, cost_basis=3000.0,
        )
        result = _allocate_lots([buy], as_of=date(2026, 4, 14))  # 468 days

        lot = result.open_lots[0]
        assert lot.days_held == 468
        assert lot.days_to_long_term == 0

    def test_no_trades_empty_result(self):
        result = _allocate_lots([], as_of=date(2026, 1, 1))
        assert result.realized_pairs == []
        assert result.open_lots == []


class TestComputeTaxPosition:
    def test_simple_st_gain(self):
        """Single short-term gain classified correctly."""
        buy = TradeFactory(
            account="Schwab", date=date(2026, 1, 10), ticker="AAPL",
            action="Buy", quantity=50.0, cost_basis=7250.0,
        )
        sell = TradeFactory(
            account="Schwab", date=date(2026, 3, 15), ticker="AAPL",
            action="Sell", quantity=50.0, proceeds=9000.0, cost_basis=7250.0,
        )
        tp = compute_tax_position([buy, sell], year=2026)

        assert tp.st_gains == 1750.0
        assert tp.st_losses == 0.0
        assert tp.lt_gains == 0.0
        assert tp.lt_losses == 0.0
        assert tp.year == 2026

    def test_lt_gain(self):
        """Long-term gain (> 365 days)."""
        buy = TradeFactory(
            account="Schwab", date=date(2025, 1, 10), ticker="AAPL",
            action="Buy", quantity=50.0, cost_basis=5000.0,
        )
        sell = TradeFactory(
            account="Schwab", date=date(2026, 3, 15), ticker="AAPL",
            action="Sell", quantity=50.0, proceeds=8000.0, cost_basis=5000.0,
        )
        tp = compute_tax_position([buy, sell], year=2026)

        assert tp.st_gains == 0.0
        assert tp.lt_gains == 3000.0

    def test_st_loss(self):
        """Short-term loss."""
        buy = TradeFactory(
            account="Schwab", date=date(2026, 1, 10), ticker="AAPL",
            action="Buy", quantity=50.0, cost_basis=9000.0,
        )
        sell = TradeFactory(
            account="Schwab", date=date(2026, 3, 15), ticker="AAPL",
            action="Sell", quantity=50.0, proceeds=7500.0, cost_basis=9000.0,
        )
        tp = compute_tax_position([buy, sell], year=2026)

        assert tp.st_gains == 0.0
        assert tp.st_losses == 1500.0

    def test_filters_by_year(self):
        """Only sells in the given year contribute to the position."""
        buy = TradeFactory(
            account="Schwab", date=date(2025, 1, 10), ticker="AAPL",
            action="Buy", quantity=50.0, cost_basis=7250.0,
        )
        sell_2025 = TradeFactory(
            account="Schwab", date=date(2025, 6, 15), ticker="AAPL",
            action="Sell", quantity=25.0, proceeds=4500.0, cost_basis=3625.0,
        )
        sell_2026 = TradeFactory(
            account="Schwab", date=date(2026, 3, 15), ticker="AAPL",
            action="Sell", quantity=25.0, proceeds=5000.0, cost_basis=3625.0,
        )
        tp = compute_tax_position([buy, sell_2025, sell_2026], year=2026)

        # Only sell_2026 counts: proceeds 5000 - basis 3625 = 1375 LT gain
        assert tp.lt_gains == 1375.0
        assert tp.st_gains == 0.0

    def test_basis_unknown_excluded_with_count(self):
        """basis_unknown sells excluded from totals, counted."""
        buy_known = TradeFactory(
            account="Schwab", date=date(2026, 1, 10), ticker="AAPL",
            action="Buy", quantity=10.0, cost_basis=1500.0,
        )
        buy_unknown = TradeFactory(
            account="Schwab", date=date(2026, 1, 15), ticker="MSFT",
            action="Buy", quantity=10.0, cost_basis=None, basis_unknown=True,
        )
        sell_known = TradeFactory(
            account="Schwab", date=date(2026, 6, 15), ticker="AAPL",
            action="Sell", quantity=10.0, proceeds=1800.0, cost_basis=1500.0,
        )
        sell_unknown = TradeFactory(
            account="Schwab", date=date(2026, 6, 20), ticker="MSFT",
            action="Sell", quantity=10.0, proceeds=2000.0, cost_basis=None,
        )
        tp = compute_tax_position(
            [buy_known, buy_unknown, sell_known, sell_unknown], year=2026
        )

        assert tp.st_gains == 300.0  # Only AAPL sell
        assert tp.basis_unknown_count == 1

    def test_option_trades_included(self):
        """Option gains/losses count toward YTD totals."""
        buy = TradeFactory(
            account="Schwab", date=date(2026, 1, 10), ticker="AAPL",
            action="Buy", quantity=1.0, cost_basis=500.0,
            option_details=OptionDetails(strike=150.0, expiry=date(2026, 6, 20), call_put="C"),
        )
        sell = TradeFactory(
            account="Schwab", date=date(2026, 3, 15), ticker="AAPL",
            action="Sell", quantity=1.0, proceeds=800.0, cost_basis=500.0,
            option_details=OptionDetails(strike=150.0, expiry=date(2026, 6, 20), call_put="C"),
        )
        tp = compute_tax_position([buy, sell], year=2026)

        assert tp.st_gains == 300.0

    def test_cross_year_buy_sell_lt(self):
        """Buy in 2025, sell in 2026 after > 365 days → long-term."""
        buy = TradeFactory(
            account="Schwab", date=date(2025, 1, 1), ticker="AAPL",
            action="Buy", quantity=10.0, cost_basis=1500.0,
        )
        sell = TradeFactory(
            account="Schwab", date=date(2026, 2, 1), ticker="AAPL",
            action="Sell", quantity=10.0, proceeds=2000.0, cost_basis=1500.0,
        )
        tp = compute_tax_position([buy, sell], year=2026)

        assert tp.lt_gains == 500.0
        assert tp.st_gains == 0.0

    def test_no_trades(self):
        tp = compute_tax_position([], year=2026)
        assert tp.st_gains == 0.0
        assert tp.st_losses == 0.0
        assert tp.lt_gains == 0.0
        assert tp.lt_losses == 0.0
        assert tp.basis_unknown_count == 0


class TestIdentifyOpenLots:
    def test_basic_open_lots(self):
        """Buys with no sells → all open."""
        buy1 = TradeFactory(
            account="Schwab", date=date(2025, 6, 1), ticker="AAPL",
            action="Buy", quantity=50.0, cost_basis=7250.0,
        )
        buy2 = TradeFactory(
            account="Robinhood", date=date(2025, 3, 1), ticker="TSLA",
            action="Buy", quantity=20.0, cost_basis=4200.0,
        )
        lots = identify_open_lots([buy1, buy2], as_of=date(2026, 4, 14))

        assert len(lots) == 2

    def test_sort_order_days_to_lt_ascending(self):
        """Lots sorted by days_to_long_term ascending, then ticker."""
        buy_far = TradeFactory(
            account="Schwab", date=date(2026, 3, 1), ticker="MSFT",
            action="Buy", quantity=15.0, cost_basis=4350.0,
        )
        buy_close = TradeFactory(
            account="Schwab", date=date(2025, 6, 1), ticker="AAPL",
            action="Buy", quantity=50.0, cost_basis=7250.0,
        )
        buy_lt = TradeFactory(
            account="Robinhood", date=date(2025, 3, 1), ticker="TSLA",
            action="Buy", quantity=20.0, cost_basis=4200.0,
        )
        lots = identify_open_lots([buy_far, buy_close, buy_lt], as_of=date(2026, 4, 14))

        assert len(lots) == 3
        assert lots[0].ticker == "AAPL"
        assert lots[1].ticker == "MSFT"
        assert lots[2].ticker == "TSLA"

    def test_options_excluded(self):
        """Option buys excluded from open lots."""
        equity_buy = TradeFactory(
            account="Schwab", date=date(2025, 6, 1), ticker="AAPL",
            action="Buy", quantity=50.0, cost_basis=7250.0,
        )
        option_buy = TradeFactory(
            account="Schwab", date=date(2025, 6, 1), ticker="AAPL",
            action="Buy", quantity=1.0, cost_basis=500.0,
            option_details=OptionDetails(strike=150.0, expiry=date(2025, 12, 20), call_put="C"),
        )
        lots = identify_open_lots([equity_buy, option_buy], as_of=date(2026, 4, 14))

        assert len(lots) == 1
        assert lots[0].is_option is False

    def test_partially_consumed_lot(self):
        """After partial sell, open lot shows remaining."""
        buy = TradeFactory(
            account="Schwab", date=date(2025, 6, 1), ticker="AAPL",
            action="Buy", quantity=100.0, cost_basis=15000.0,
        )
        sell = TradeFactory(
            account="Schwab", date=date(2025, 9, 1), ticker="AAPL",
            action="Sell", quantity=60.0, proceeds=10200.0, cost_basis=9000.0,
        )
        lots = identify_open_lots([buy, sell], as_of=date(2026, 4, 14))

        assert len(lots) == 1
        assert lots[0].quantity == 40.0
        assert lots[0].adjusted_basis_per_share == 150.0

    def test_no_trades(self):
        lots = identify_open_lots([], as_of=date(2026, 1, 1))
        assert lots == []


class TestSelectLots:
    def _make_open_lots(self):
        """Helper: 3 open lots at different prices and holding periods."""
        return [
            OpenLotFactory(
                ticker="AAPL", account="Schwab", quantity=50.0,
                adjusted_basis_per_share=145.0,
                purchase_date=date(2025, 8, 15), days_held=242, days_to_long_term=124,
            ),
            OpenLotFactory(
                ticker="AAPL", account="Robinhood", quantity=50.0,
                adjusted_basis_per_share=112.0,
                purchase_date=date(2025, 1, 10), days_held=459, days_to_long_term=0,
            ),
            OpenLotFactory(
                ticker="AAPL", account="Schwab", quantity=50.0,
                adjusted_basis_per_share=195.0,
                purchase_date=date(2025, 11, 20), days_held=145, days_to_long_term=221,
            ),
        ]

    def test_fifo_selects_earliest_first(self):
        lots = self._make_open_lots()
        sel = select_lots(lots, ticker="AAPL", qty=50.0, method="FIFO", price=180.0)

        assert sel.method == "FIFO"
        assert len(sel.lots_used) == 1
        # Earliest: Jan 10 at $112
        assert sel.lots_used[0].purchase_date == date(2025, 1, 10)
        assert sel.total_gain_loss == 3400.0  # (180 - 112) * 50
        assert sel.lt_gain_loss == 3400.0  # long-term lot
        assert sel.st_gain_loss == 0.0

    def test_hifo_selects_highest_basis_first(self):
        lots = self._make_open_lots()
        sel = select_lots(lots, ticker="AAPL", qty=50.0, method="HIFO", price=180.0)

        assert sel.method == "HIFO"
        assert sel.lots_used[0].adjusted_basis_per_share == 195.0
        assert sel.total_gain_loss == -750.0  # (180 - 195) * 50
        assert sel.st_gain_loss == -750.0  # short-term lot

    def test_lifo_selects_most_recent_first(self):
        lots = self._make_open_lots()
        sel = select_lots(lots, ticker="AAPL", qty=50.0, method="LIFO", price=180.0)

        assert sel.method == "LIFO"
        assert sel.lots_used[0].purchase_date == date(2025, 11, 20)
        assert sel.total_gain_loss == -750.0

    def test_fifo_partial_lot_split(self):
        """FIFO across two lots, producing both ST and LT components."""
        lots = self._make_open_lots()
        # Need 80 shares: 50 from Jan 10 (LT) + 30 from Aug 15 (ST)
        sel = select_lots(lots, ticker="AAPL", qty=80.0, method="FIFO", price=180.0)

        assert len(sel.lots_used) == 2
        assert sel.lt_gain_loss == 3400.0  # (180-112)*50
        assert sel.st_gain_loss == 1050.0  # (180-145)*30
        assert sel.total_gain_loss == 4450.0

    def test_quantity_exceeds_available(self):
        """Requesting more than available → returns None."""
        lots = self._make_open_lots()  # 150 total
        sel = select_lots(lots, ticker="AAPL", qty=200.0, method="FIFO", price=180.0)

        assert sel is None

    def test_no_matching_ticker(self):
        lots = self._make_open_lots()  # all AAPL
        sel = select_lots(lots, ticker="TSLA", qty=10.0, method="FIFO", price=300.0)

        assert sel is None

    def test_wash_sale_risk_defaults_false(self):
        lots = self._make_open_lots()
        sel = select_lots(lots, ticker="AAPL", qty=50.0, method="HIFO", price=180.0)

        assert sel.wash_sale_risk is False

    def test_pools_across_accounts(self):
        """Lots from Schwab and Robinhood are both available."""
        lots = self._make_open_lots()
        sel = select_lots(lots, ticker="AAPL", qty=150.0, method="FIFO", price=180.0)

        assert sel is not None
        assert len(sel.lots_used) == 3
        accounts = {lot.account for lot in sel.lots_used}
        assert accounts == {"Schwab", "Robinhood"}


class TestRecommendLotMethod:
    def _make_tax_position(self, st_gains=0.0, st_losses=0.0, lt_gains=0.0, lt_losses=0.0):
        return TaxPosition(
            st_gains=st_gains, st_losses=st_losses,
            lt_gains=lt_gains, lt_losses=lt_losses,
            year=2026, basis_unknown_count=0,
        )

    def _make_selection(self, method, st_gain_loss=0.0, lt_gain_loss=0.0, wash_sale_risk=False):
        return LotSelection(
            method=method,
            lots_used=[],
            st_gain_loss=st_gain_loss,
            lt_gain_loss=lt_gain_loss,
            total_gain_loss=st_gain_loss + lt_gain_loss,
            wash_sale_risk=wash_sale_risk,
        )

    def test_prefer_st_loss_offset(self):
        """User has ST gains, LIFO produces ST loss → prefer LIFO."""
        tp = self._make_tax_position(st_gains=9200.0)
        selections = {
            "FIFO": self._make_selection("FIFO", st_gain_loss=1750.0),
            "HIFO": self._make_selection("HIFO", lt_gain_loss=3400.0),
            "LIFO": self._make_selection("LIFO", st_gain_loss=-750.0),
        }
        rec = recommend_lot_method(selections, tp)

        assert rec.preferred_method == "LIFO"
        assert rec.reason == "st_loss_offset"
        assert rec.has_wash_risk is False

    def test_st_loss_with_wash_risk_falls_through(self):
        """LIFO produces ST loss but has wash risk → flag + fallback."""
        tp = self._make_tax_position(st_gains=9200.0)
        selections = {
            "FIFO": self._make_selection("FIFO", st_gain_loss=1750.0),
            "HIFO": self._make_selection("HIFO", lt_gain_loss=3400.0),
            "LIFO": self._make_selection("LIFO", st_gain_loss=-750.0, wash_sale_risk=True),
        }
        rec = recommend_lot_method(selections, tp, safe_sell_date=date(2026, 1, 15))

        assert rec.preferred_method == "LIFO"
        assert rec.reason == "st_loss_offset"
        assert rec.has_wash_risk is True
        assert rec.safe_sell_date == date(2026, 1, 15)
        assert rec.fallback_method is not None

    def test_prefer_lt_gain_over_st_gain(self):
        """No losses available, HIFO is LT gain, FIFO is ST gain → prefer HIFO."""
        tp = self._make_tax_position(st_gains=5000.0)
        selections = {
            "FIFO": self._make_selection("FIFO", st_gain_loss=1750.0),
            "HIFO": self._make_selection("HIFO", lt_gain_loss=500.0),
            "LIFO": self._make_selection("LIFO", st_gain_loss=3000.0),
        }
        rec = recommend_lot_method(selections, tp)

        assert rec.preferred_method == "HIFO"
        assert rec.reason == "lt_lower_rate"

    def test_prefer_smallest_gain(self):
        """All methods produce ST gains → prefer smallest."""
        tp = self._make_tax_position(st_gains=5000.0)
        selections = {
            "FIFO": self._make_selection("FIFO", st_gain_loss=1750.0),
            "HIFO": self._make_selection("HIFO", st_gain_loss=500.0),
            "LIFO": self._make_selection("LIFO", st_gain_loss=3000.0),
        }
        rec = recommend_lot_method(selections, tp)

        assert rec.preferred_method == "HIFO"
        assert rec.reason == "least_gain"

    def test_all_methods_produce_same_treatment_prefer_smallest(self):
        """All LT gains → prefer smallest."""
        tp = self._make_tax_position()
        selections = {
            "FIFO": self._make_selection("FIFO", lt_gain_loss=2000.0),
            "HIFO": self._make_selection("HIFO", lt_gain_loss=800.0),
            "LIFO": self._make_selection("LIFO", lt_gain_loss=1500.0),
        }
        rec = recommend_lot_method(selections, tp)

        assert rec.preferred_method == "HIFO"
        assert rec.reason == "least_gain"

    def test_all_methods_have_wash_risk(self):
        """All methods produce losses with wash risk → no clean option."""
        tp = self._make_tax_position(st_gains=5000.0)
        selections = {
            "FIFO": self._make_selection("FIFO", st_gain_loss=-500.0, wash_sale_risk=True),
            "HIFO": self._make_selection("HIFO", st_gain_loss=-1000.0, wash_sale_risk=True),
            "LIFO": self._make_selection("LIFO", st_gain_loss=-750.0, wash_sale_risk=True),
        }
        rec = recommend_lot_method(selections, tp, safe_sell_date=date(2026, 1, 15))

        assert rec.has_wash_risk is True
        assert rec.fallback_method is None

    def test_tiebreak_fifo(self):
        """All methods produce identical results → prefer FIFO."""
        tp = self._make_tax_position()
        selections = {
            "FIFO": self._make_selection("FIFO", st_gain_loss=1000.0),
            "HIFO": self._make_selection("HIFO", st_gain_loss=1000.0),
            "LIFO": self._make_selection("LIFO", st_gain_loss=1000.0),
        }
        rec = recommend_lot_method(selections, tp)

        assert rec.preferred_method == "FIFO"
