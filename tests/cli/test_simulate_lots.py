from datetime import date
from unittest.mock import patch

from typer.testing import CliRunner

from net_alpha.cli.app import app
from net_alpha.models.domain import (
    LotRecommendation,
    LotSelection,
    OpenLot,
    TaxPosition,
)

runner = CliRunner()


def _make_open_lot(ticker="AAPL", account="Schwab", qty=50.0, basis=145.0,
                    purchase_date=date(2025, 8, 15), days_held=242, days_to_lt=124):
    return OpenLot(
        ticker=ticker, account=account, quantity=qty,
        adjusted_basis_per_share=basis, purchase_date=purchase_date,
        days_held=days_held, days_to_long_term=days_to_lt,
        basis_unknown=False, is_option=False,
    )


class TestSimulateSellLotSelection:
    @patch("net_alpha.cli.simulate._get_lot_selection_data")
    @patch("net_alpha.cli.simulate._find_lookback_triggers")
    @patch("net_alpha.cli.simulate._bootstrap_and_load")
    def test_lot_table_shown_when_price_given(self, mock_boot, mock_lookback, mock_lots):
        mock_boot.return_value = ([], {}, None)
        mock_lookback.return_value = []
        mock_lots.return_value = (
            {
                "FIFO": LotSelection(
                    method="FIFO", lots_used=[_make_open_lot()],
                    st_gain_loss=1750.0, lt_gain_loss=0.0,
                    total_gain_loss=1750.0, wash_sale_risk=False,
                ),
                "HIFO": LotSelection(
                    method="HIFO", lots_used=[_make_open_lot(basis=112.0)],
                    st_gain_loss=0.0, lt_gain_loss=3400.0,
                    total_gain_loss=3400.0, wash_sale_risk=False,
                ),
                "LIFO": LotSelection(
                    method="LIFO", lots_used=[_make_open_lot(basis=195.0)],
                    st_gain_loss=-750.0, lt_gain_loss=0.0,
                    total_gain_loss=-750.0, wash_sale_risk=False,
                ),
            },
            LotRecommendation(
                preferred_method="LIFO", reason="st_loss_offset",
                has_wash_risk=False, safe_sell_date=None,
                fallback_method=None, fallback_reason=None,
            ),
        )
        result = runner.invoke(app, ["simulate", "sell", "AAPL", "50", "--price", "180"])

        assert result.exit_code == 0
        assert "LOT SELECTION" in result.output
        assert "FIFO" in result.output
        assert "HIFO" in result.output
        assert "LIFO" in result.output
        assert "Recommendation" in result.output

    @patch("net_alpha.cli.simulate._find_lookback_triggers")
    @patch("net_alpha.cli.simulate._bootstrap_and_load")
    def test_lot_table_not_shown_without_price(self, mock_boot, mock_lookback):
        mock_boot.return_value = ([], {}, None)
        mock_lookback.return_value = []
        result = runner.invoke(app, ["simulate", "sell", "AAPL", "50"])

        assert result.exit_code == 0
        assert "LOT SELECTION" not in result.output

    @patch("net_alpha.cli.simulate._get_lot_selection_data")
    @patch("net_alpha.cli.simulate._find_lookback_triggers")
    @patch("net_alpha.cli.simulate._bootstrap_and_load")
    def test_no_open_lots_message(self, mock_boot, mock_lookback, mock_lots):
        mock_boot.return_value = ([], {}, None)
        mock_lookback.return_value = []
        mock_lots.return_value = (None, None)
        result = runner.invoke(app, ["simulate", "sell", "AAPL", "50", "--price", "180"])

        assert result.exit_code == 0
        assert "No open lots" in result.output or "no open lots" in result.output

    @patch("net_alpha.cli.simulate._get_lot_selection_data")
    @patch("net_alpha.cli.simulate._find_lookback_triggers")
    @patch("net_alpha.cli.simulate._bootstrap_and_load")
    def test_wash_risk_shown_in_table(self, mock_boot, mock_lookback, mock_lots):
        mock_boot.return_value = ([], {}, None)
        mock_lookback.return_value = []
        mock_lots.return_value = (
            {
                "FIFO": LotSelection(
                    method="FIFO", lots_used=[_make_open_lot()],
                    st_gain_loss=1750.0, lt_gain_loss=0.0,
                    total_gain_loss=1750.0, wash_sale_risk=False,
                ),
                "HIFO": LotSelection(
                    method="HIFO", lots_used=[_make_open_lot(basis=112.0)],
                    st_gain_loss=0.0, lt_gain_loss=3400.0,
                    total_gain_loss=3400.0, wash_sale_risk=False,
                ),
                "LIFO": LotSelection(
                    method="LIFO", lots_used=[_make_open_lot(basis=195.0)],
                    st_gain_loss=-750.0, lt_gain_loss=0.0,
                    total_gain_loss=-750.0, wash_sale_risk=True,
                ),
            },
            LotRecommendation(
                preferred_method="LIFO", reason="st_loss_offset",
                has_wash_risk=True, safe_sell_date=date(2026, 1, 15),
                fallback_method="FIFO", fallback_reason="least_gain",
            ),
        )
        result = runner.invoke(app, ["simulate", "sell", "AAPL", "50", "--price", "180"])

        assert "Risk" in result.output or "\u26a0" in result.output
