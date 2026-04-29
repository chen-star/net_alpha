from datetime import date

from net_alpha.models.domain import OptionDetails, Trade
from net_alpha.section_1256.universe import is_section_1256, load_universe, universe_hash


def _option_trade(ticker: str, *, action: str = "buy") -> Trade:
    return Trade(
        id=f"{ticker}-{action}-{date.today().isoformat()}",
        date=date.today(),
        account="test/personal",
        ticker=ticker,
        action=action,
        quantity=1,
        proceeds=100,
        cost_basis=100,
        option_details=OptionDetails(strike=4500, expiry=date(2025, 12, 19), call_put="C"),
    )


def _stock_trade(ticker: str) -> Trade:
    return Trade(
        id=f"{ticker}-stock",
        date=date.today(),
        account="test/personal",
        ticker=ticker,
        action="buy",
        quantity=10,
        proceeds=1000,
        cost_basis=1000,
        option_details=None,
    )


def test_is_section_1256_true_for_spx_option():
    assert is_section_1256(_option_trade("SPX")) is True


def test_is_section_1256_true_for_ndx_option():
    assert is_section_1256(_option_trade("NDX")) is True


def test_is_section_1256_false_for_spy_option():
    assert is_section_1256(_option_trade("SPY")) is False


def test_is_section_1256_false_for_qqq_option():
    assert is_section_1256(_option_trade("QQQ")) is False


def test_is_section_1256_false_for_stock_trade_even_if_ticker_in_universe():
    assert is_section_1256(_stock_trade("SPX")) is False


def test_is_section_1256_false_for_aapl_option():
    assert is_section_1256(_option_trade("AAPL")) is False


def test_load_universe_contains_bundled_symbols():
    syms = load_universe()
    assert {"SPX", "NDX", "RUT", "VIX", "OEX", "XSP", "MXEF", "MXEA"}.issubset(syms)


def test_load_universe_user_override_extends(tmp_path):
    user_yaml = tmp_path / "section_1256_underlyings.yaml"
    user_yaml.write_text("broad_based_index_options:\n  - DJX\n")
    syms = load_universe(user_path=user_yaml)
    assert "SPX" in syms
    assert "DJX" in syms


def test_universe_hash_deterministic():
    assert universe_hash() == universe_hash()


def test_universe_hash_changes_with_user_override(tmp_path):
    base = universe_hash()
    user_yaml = tmp_path / "section_1256_underlyings.yaml"
    user_yaml.write_text("broad_based_index_options:\n  - DJX\n")
    extended = universe_hash(user_path=user_yaml)
    assert base != extended
