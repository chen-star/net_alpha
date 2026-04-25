from datetime import date
from pathlib import Path

from net_alpha.import_.csv_reader import SchemaMapping, read_csv_with_mapping

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_schwab_golden_file():
    mapping = SchemaMapping(
        date="Date",
        ticker="Symbol",
        action="Action",
        quantity="Quantity",
        proceeds="Amount",
        cost_basis="Cost Basis",
        buy_values=["Buy", "Reinvest"],
        sell_values=["Sell"],
        option_format="schwab_human",
    )
    trades = read_csv_with_mapping(
        csv_path=FIXTURES / "schwab_sample.csv",
        mapping=mapping,
        account="Schwab",
        schema_cache_id="test",
    )
    assert len(trades) == 4

    # Verify specific trade details
    buy_tsla = trades[0]
    assert buy_tsla.ticker == "TSLA"
    assert buy_tsla.action == "Buy"
    assert buy_tsla.quantity == 10.0
    assert buy_tsla.date == date(2024, 10, 15)

    # Option trade
    option = trades[2]
    assert option.ticker == "TSLA"
    assert option.is_option()
    assert option.option_details.strike == 250.0


def test_robinhood_golden_file():
    mapping = SchemaMapping(
        date="Activity Date",
        ticker="Instrument",
        action="Trans Code",
        quantity="Quantity",
        proceeds="Amount",
        cost_basis=None,
        buy_values=["Buy"],
        sell_values=["Sell"],
        option_format="robinhood_human",
    )
    trades = read_csv_with_mapping(
        csv_path=FIXTURES / "robinhood_sample.csv",
        mapping=mapping,
        account="Robinhood",
        schema_cache_id="test",
    )
    assert len(trades) == 4

    sell_tsla = trades[1]
    assert sell_tsla.ticker == "TSLA"
    assert sell_tsla.action == "Sell"
    assert sell_tsla.proceeds == 2000.0
    assert sell_tsla.basis_unknown is True

    option = trades[2]
    assert option.ticker == "TSLA"
    assert option.is_option()
    assert option.option_details.strike == 250.0
    assert option.option_details.call_put == "C"
