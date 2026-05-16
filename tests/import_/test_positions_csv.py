from pathlib import Path

import pytest

from net_alpha.import_.positions_csv import (
    PositionsCSVParseError,
    parse_positions_csv,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "positions"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text()


def test_per_account_header_parses():
    rows, as_of = parse_positions_csv(_load("per_account_basic.csv"))
    assert as_of == "2026-05-16"
    assert len(rows) > 0
    assert all(r["account_label"] == "Demo Account ...999" for r in rows)


def test_per_account_skips_cash_and_futures_and_total():
    rows, _ = parse_positions_csv(_load("per_account_basic.csv"))
    symbols = {r["symbol"] for r in rows}
    assert "Cash & Cash Investments" not in symbols
    assert "Futures Cash" not in symbols
    assert "Futures Positions Market Value" not in symbols
    assert "Positions Total" not in symbols


def test_per_account_skips_option_rows():
    """Per-account file includes option contracts; we keep equity-only to match
    the existing reconciliation scope (aggregate_open_positions is equity-only).
    """
    rows, _ = parse_positions_csv(_load("per_account_basic.csv"))
    for r in rows:
        # Schwab option symbols contain a space-delimited expiry like
        # "EU 06/18/2026 2.00 P". No equity ticker has spaces.
        assert " " not in r["symbol"], f"option-shaped symbol leaked through: {r['symbol']!r}"


def test_per_account_empty_returns_empty_rows():
    rows, as_of = parse_positions_csv(_load("per_account_empty.csv"))
    assert as_of == "2026-05-16"
    assert rows == []


def test_per_account_invalid_header_raises():
    with pytest.raises(PositionsCSVParseError):
        parse_positions_csv('"Random unrelated CSV"\nSymbol,Qty\nAAPL,100\n')


def test_all_accounts_format_still_works():
    """Regression: existing all-accounts path must remain unchanged."""
    rows, as_of = parse_positions_csv(
        '"Positions for All Accounts as of 04:00 PM ET, 2026/05/16"\n'
        "Account,Symbol,Quantity,Cost Basis,Market Value,Gain $\n"
        '"Brokerage ...123","AAPL","100","$15,000","$18,000","$3,000"\n'
        '"Brokerage ...123","Account Total","--","--","--","--"\n'
    )
    assert as_of == "2026-05-16"
    assert len(rows) == 1
    assert rows[0]["account_label"] == "Brokerage ...123"
    assert rows[0]["symbol"] == "AAPL"
