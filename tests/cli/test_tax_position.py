from datetime import date
from unittest.mock import patch

from typer.testing import CliRunner

from net_alpha.cli.app import app
from net_alpha.models.domain import OpenLot, TaxPosition

runner = CliRunner()


class TestTaxPositionCommand:
    @patch("net_alpha.cli.tax_position._load_trades_and_compute")
    def test_basic_output(self, mock_load):
        """Renders tax position and open lots."""
        mock_load.return_value = (
            TaxPosition(
                st_gains=12400.0,
                st_losses=3200.0,
                lt_gains=8100.0,
                lt_losses=500.0,
                year=2026,
                basis_unknown_count=0,
            ),
            [
                OpenLot(
                    ticker="AAPL",
                    account="Schwab",
                    quantity=50.0,
                    adjusted_basis_per_share=145.0,
                    purchase_date=date(2025, 6, 1),
                    days_held=315,
                    days_to_long_term=50,
                    basis_unknown=False,
                    is_option=False,
                ),
            ],
        )
        result = runner.invoke(app, ["tax-position", "--year", "2026"])

        assert result.exit_code == 0
        assert "TAX POSITION" in result.output
        assert "$12,400.00" in result.output
        assert "$3,200.00" in result.output
        assert "$8,100.00" in result.output
        assert "AAPL" in result.output
        assert "Schwab" in result.output
        assert "50 days" in result.output
        assert "consult a tax professional" in result.output.lower() or "informational only" in result.output.lower()

    @patch("net_alpha.cli.tax_position._load_trades_and_compute")
    def test_carryforward_shown_when_above_3000(self, mock_load):
        mock_load.return_value = (
            TaxPosition(
                st_gains=0.0,
                st_losses=4800.0,
                lt_gains=0.0,
                lt_losses=0.0,
                year=2026,
                basis_unknown_count=0,
            ),
            [],
        )
        result = runner.invoke(app, ["tax-position", "--year", "2026"])

        assert "carryforward" in result.output.lower() or "carry" in result.output.lower()
        assert "$1,800.00" in result.output

    @patch("net_alpha.cli.tax_position._load_trades_and_compute")
    def test_carryforward_hidden_when_under_3000(self, mock_load):
        mock_load.return_value = (
            TaxPosition(
                st_gains=0.0,
                st_losses=2000.0,
                lt_gains=0.0,
                lt_losses=0.0,
                year=2026,
                basis_unknown_count=0,
            ),
            [],
        )
        result = runner.invoke(app, ["tax-position", "--year", "2026"])

        assert "carryforward" not in result.output.lower()

    @patch("net_alpha.cli.tax_position._load_trades_and_compute")
    def test_basis_unknown_warning(self, mock_load):
        mock_load.return_value = (
            TaxPosition(
                st_gains=300.0,
                st_losses=0.0,
                lt_gains=0.0,
                lt_losses=0.0,
                year=2026,
                basis_unknown_count=3,
            ),
            [],
        )
        result = runner.invoke(app, ["tax-position", "--year", "2026"])

        assert "3" in result.output
        assert "unknown" in result.output.lower()

    @patch("net_alpha.cli.tax_position._load_trades_and_compute")
    def test_long_term_lots_shown(self, mock_load):
        mock_load.return_value = (
            TaxPosition(
                st_gains=0.0,
                st_losses=0.0,
                lt_gains=0.0,
                lt_losses=0.0,
                year=2026,
                basis_unknown_count=0,
            ),
            [
                OpenLot(
                    ticker="TSLA",
                    account="Robinhood",
                    quantity=20.0,
                    adjusted_basis_per_share=210.0,
                    purchase_date=date(2025, 3, 1),
                    days_held=390,
                    days_to_long_term=0,
                    basis_unknown=False,
                    is_option=False,
                ),
            ],
        )
        result = runner.invoke(app, ["tax-position", "--year", "2026"])

        assert "TSLA" in result.output
        assert "Long-term" in result.output or "long-term" in result.output or "✓" in result.output

    @patch("net_alpha.cli.tax_position._load_trades_and_compute")
    def test_basis_unknown_lot_shown_as_unknown(self, mock_load):
        mock_load.return_value = (
            TaxPosition(
                st_gains=0.0,
                st_losses=0.0,
                lt_gains=0.0,
                lt_losses=0.0,
                year=2026,
                basis_unknown_count=0,
            ),
            [
                OpenLot(
                    ticker="MSFT",
                    account="Schwab",
                    quantity=10.0,
                    adjusted_basis_per_share=0.0,
                    purchase_date=date(2025, 6, 1),
                    days_held=317,
                    days_to_long_term=49,
                    basis_unknown=True,
                    is_option=False,
                ),
            ],
        )
        result = runner.invoke(app, ["tax-position", "--year", "2026"])

        assert "Unknown" in result.output or "unknown" in result.output
