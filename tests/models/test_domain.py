from datetime import date

from net_alpha.models.domain import (
    AllocationResult,
    DetectionResult,
    Lot,
    LotRecommendation,
    LotSelection,
    OpenLot,
    OptionDetails,
    RealizedPair,
    TaxPosition,
    Trade,
    WashSaleViolation,
)


def test_trade_equity_loss():
    trade = Trade(
        account="Schwab",
        date=date(2024, 10, 15),
        ticker="TSLA",
        action="Sell",
        quantity=10.0,
        proceeds=2400.0,
        cost_basis=3600.0,
    )
    assert trade.is_sell() is True
    assert trade.is_buy() is False
    assert trade.is_option() is False
    assert trade.is_loss() is True
    assert trade.loss_amount() == 1200.0


def test_trade_equity_gain():
    trade = Trade(
        account="Schwab",
        date=date(2024, 10, 15),
        ticker="TSLA",
        action="Sell",
        quantity=10.0,
        proceeds=5000.0,
        cost_basis=3600.0,
    )
    assert trade.is_loss() is False
    assert trade.loss_amount() == 0.0


def test_trade_buy_is_never_loss():
    trade = Trade(
        account="Schwab",
        date=date(2024, 10, 15),
        ticker="TSLA",
        action="Buy",
        quantity=10.0,
        cost_basis=3600.0,
    )
    assert trade.is_loss() is False


def test_trade_basis_unknown_is_never_loss():
    trade = Trade(
        account="Schwab",
        date=date(2024, 10, 15),
        ticker="TSLA",
        action="Sell",
        quantity=10.0,
        proceeds=2400.0,
        basis_unknown=True,
    )
    assert trade.is_loss() is False
    assert trade.loss_amount() == 0.0


def test_trade_with_option_details():
    trade = Trade(
        account="Schwab",
        date=date(2024, 10, 15),
        ticker="TSLA",
        action="Buy",
        quantity=1.0,
        cost_basis=500.0,
        option_details=OptionDetails(
            strike=250.0,
            expiry=date(2024, 12, 20),
            call_put="C",
        ),
    )
    assert trade.is_option() is True
    assert trade.option_details.strike == 250.0
    assert trade.option_details.call_put == "C"


def test_trade_id_auto_generated():
    t1 = Trade(account="A", date=date(2024, 1, 1), ticker="X", action="Buy", quantity=1.0)  # noqa: E501
    t2 = Trade(account="A", date=date(2024, 1, 1), ticker="X", action="Buy", quantity=1.0)  # noqa: E501
    assert t1.id != t2.id
    assert len(t1.id) == 36  # UUID format


def test_lot_from_trade():
    trade = Trade(
        account="Robinhood",
        date=date(2024, 11, 3),
        ticker="TSLA",
        action="Buy",
        quantity=15.0,
        cost_basis=3600.0,
    )
    lot = Lot.from_trade(trade)
    assert lot.trade_id == trade.id
    assert lot.account == "Robinhood"
    assert lot.ticker == "TSLA"
    assert lot.quantity == 15.0
    assert lot.cost_basis == 3600.0
    assert lot.adjusted_basis == 3600.0


def test_lot_from_option_trade():
    trade = Trade(
        account="Schwab",
        date=date(2024, 11, 3),
        ticker="TSLA",
        action="Buy",
        quantity=1.0,
        cost_basis=500.0,
        option_details=OptionDetails(strike=250.0, expiry=date(2024, 12, 20), call_put="C"),
    )
    lot = Lot.from_trade(trade)
    assert lot.option_details is not None
    assert lot.option_details.strike == 250.0


def test_wash_sale_violation():
    violation = WashSaleViolation(
        loss_trade_id="sell_1",
        replacement_trade_id="buy_1",
        confidence="Confirmed",
        disallowed_loss=1200.0,
        matched_quantity=10.0,
    )
    assert violation.confidence == "Confirmed"
    assert violation.disallowed_loss == 1200.0


def test_detection_result():
    result = DetectionResult(violations=[], lots=[], basis_unknown_count=0)
    assert result.violations == []
    assert result.lots == []
    assert result.basis_unknown_count == 0


class TestTaxPosition:
    def test_net_st_gains(self):
        tp = TaxPosition(
            st_gains=12400.0, st_losses=3200.0,
            lt_gains=0.0, lt_losses=0.0,
            year=2026, basis_unknown_count=0,
        )
        assert tp.net_st == 9200.0

    def test_net_st_losses(self):
        tp = TaxPosition(
            st_gains=1000.0, st_losses=5000.0,
            lt_gains=0.0, lt_losses=0.0,
            year=2026, basis_unknown_count=0,
        )
        assert tp.net_st == -4000.0

    def test_net_lt(self):
        tp = TaxPosition(
            st_gains=0.0, st_losses=0.0,
            lt_gains=8100.0, lt_losses=500.0,
            year=2026, basis_unknown_count=0,
        )
        assert tp.net_lt == 7600.0

    def test_net_capital_gain(self):
        tp = TaxPosition(
            st_gains=12400.0, st_losses=3200.0,
            lt_gains=8100.0, lt_losses=500.0,
            year=2026, basis_unknown_count=0,
        )
        assert tp.net_capital_gain == 16800.0

    def test_loss_needed_to_zero_st_positive(self):
        tp = TaxPosition(
            st_gains=9200.0, st_losses=0.0,
            lt_gains=0.0, lt_losses=0.0,
            year=2026, basis_unknown_count=0,
        )
        assert tp.loss_needed_to_zero_st == 9200.0

    def test_loss_needed_to_zero_st_already_negative(self):
        tp = TaxPosition(
            st_gains=1000.0, st_losses=5000.0,
            lt_gains=0.0, lt_losses=0.0,
            year=2026, basis_unknown_count=0,
        )
        assert tp.loss_needed_to_zero_st == 0.0

    def test_carryforward_no_loss(self):
        tp = TaxPosition(
            st_gains=5000.0, st_losses=0.0,
            lt_gains=0.0, lt_losses=0.0,
            year=2026, basis_unknown_count=0,
        )
        assert tp.carryforward == 0.0

    def test_carryforward_loss_under_3000(self):
        tp = TaxPosition(
            st_gains=0.0, st_losses=2999.0,
            lt_gains=0.0, lt_losses=0.0,
            year=2026, basis_unknown_count=0,
        )
        assert tp.carryforward == 0.0

    def test_carryforward_loss_exactly_3000(self):
        tp = TaxPosition(
            st_gains=0.0, st_losses=3000.0,
            lt_gains=0.0, lt_losses=0.0,
            year=2026, basis_unknown_count=0,
        )
        assert tp.carryforward == 0.0

    def test_carryforward_loss_above_3000(self):
        tp = TaxPosition(
            st_gains=0.0, st_losses=4800.0,
            lt_gains=0.0, lt_losses=0.0,
            year=2026, basis_unknown_count=0,
        )
        assert tp.carryforward == 1800.0

    def test_carryforward_lt_gains_offset_st_losses(self):
        # net_st = -2000, net_lt = +1500 → net_capital_gain = -500 → carryforward = 0
        tp = TaxPosition(
            st_gains=0.0, st_losses=2000.0,
            lt_gains=1500.0, lt_losses=0.0,
            year=2026, basis_unknown_count=0,
        )
        assert tp.carryforward == 0.0


class TestOpenLot:
    def test_creation(self):
        lot = OpenLot(
            ticker="AAPL",
            account="Schwab",
            quantity=50.0,
            adjusted_basis_per_share=145.0,
            purchase_date=date(2025, 6, 1),
            days_held=315,
            days_to_long_term=50,
            basis_unknown=False,
            is_option=False,
        )
        assert lot.ticker == "AAPL"
        assert lot.days_to_long_term == 50

    def test_long_term_lot(self):
        lot = OpenLot(
            ticker="TSLA",
            account="Robinhood",
            quantity=20.0,
            adjusted_basis_per_share=210.0,
            purchase_date=date(2025, 3, 1),
            days_held=390,
            days_to_long_term=0,
            basis_unknown=False,
            is_option=False,
        )
        assert lot.days_to_long_term == 0


class TestLotSelection:
    def test_creation_with_st_lt_split(self):
        sel = LotSelection(
            method="FIFO",
            lots_used=[],
            st_gain_loss=1750.0,
            lt_gain_loss=0.0,
            total_gain_loss=1750.0,
            wash_sale_risk=False,
        )
        assert sel.st_gain_loss == 1750.0
        assert sel.lt_gain_loss == 0.0


class TestLotRecommendation:
    def test_with_wash_risk(self):
        rec = LotRecommendation(
            preferred_method="LIFO",
            reason="st_loss_offset",
            has_wash_risk=True,
            safe_sell_date=date(2026, 1, 15),
            fallback_method="FIFO",
            fallback_reason="least_gain",
        )
        assert rec.has_wash_risk is True
        assert rec.fallback_method == "FIFO"

    def test_no_wash_risk(self):
        rec = LotRecommendation(
            preferred_method="HIFO",
            reason="lt_lower_rate",
            has_wash_risk=False,
            safe_sell_date=None,
            fallback_method=None,
            fallback_reason=None,
        )
        assert rec.has_wash_risk is False


class TestRealizedPair:
    def test_creation(self):
        pair = RealizedPair(
            sell_trade_id="sell-1",
            buy_lot_date=date(2025, 1, 15),
            buy_lot_account="Schwab",
            quantity=10.0,
            proceeds=1800.0,
            basis=1500.0,
            basis_unknown=False,
            is_long_term=False,
        )
        assert pair.quantity == 10.0
        assert pair.is_long_term is False

    def test_basis_unknown(self):
        pair = RealizedPair(
            sell_trade_id="sell-2",
            buy_lot_date=date(2025, 1, 15),
            buy_lot_account="Schwab",
            quantity=5.0,
            proceeds=0.0,
            basis=0.0,
            basis_unknown=True,
            is_long_term=False,
        )
        assert pair.basis_unknown is True


class TestAllocationResult:
    def test_empty(self):
        result = AllocationResult(realized_pairs=[], open_lots=[])
        assert result.realized_pairs == []
        assert result.open_lots == []
