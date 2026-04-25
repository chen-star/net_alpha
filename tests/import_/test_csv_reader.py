from datetime import date
from pathlib import Path

from net_alpha.import_.csv_reader import SchemaMapping, compute_header_hash, read_csv_with_mapping

FIXTURES = Path(__file__).parent.parent / "fixtures"

SCHWAB_MAPPING = SchemaMapping(
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


def test_read_schwab_csv():
    trades = read_csv_with_mapping(
        csv_path=FIXTURES / "schwab_sample.csv",
        mapping=SCHWAB_MAPPING,
        account="Schwab",
        schema_cache_id="sc1",
    )
    assert len(trades) == 4

    # First trade: equity buy
    t0 = trades[0]
    assert t0.account == "Schwab"
    assert t0.ticker == "TSLA"
    assert t0.action == "Buy"
    assert t0.quantity == 10.0
    assert t0.proceeds == 2400.0
    assert t0.date == date(2024, 10, 15)
    assert t0.is_option() is False
    assert t0.schema_cache_id == "sc1"
    assert t0.raw_row_hash is not None

    # Second trade: equity sell
    t1 = trades[1]
    assert t1.action == "Sell"
    assert t1.is_loss() is True

    # Third trade: option buy
    t2 = trades[2]
    assert t2.ticker == "TSLA"  # Underlying extracted
    assert t2.is_option() is True
    assert t2.option_details.strike == 250.0
    assert t2.option_details.call_put == "C"

    # Fourth trade: reinvest mapped to Buy
    t3 = trades[3]
    assert t3.action == "Buy"
    assert t3.ticker == "AAPL"


def test_compute_header_hash():
    h1 = compute_header_hash(["Date", "Symbol", "Action"])
    h2 = compute_header_hash(["Date", "Symbol", "Action"])
    h3 = compute_header_hash(["Date", "Ticker", "Action"])
    assert h1 == h2
    assert h1 != h3


def test_missing_cost_basis_marked():
    """When cost_basis column is None in mapping, trades are marked basis_unknown."""
    mapping = SchemaMapping(
        date="Date",
        ticker="Symbol",
        action="Action",
        quantity="Quantity",
        proceeds="Amount",
        cost_basis=None,
        buy_values=["Buy", "Reinvest"],
        sell_values=["Sell"],
    )
    trades = read_csv_with_mapping(
        csv_path=FIXTURES / "schwab_sample.csv",
        mapping=mapping,
        account="Schwab",
        schema_cache_id="sc1",
    )
    assert all(t.basis_unknown for t in trades)
