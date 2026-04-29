"""§1256 contracts produce ExemptMatch instead of WashSaleViolation.
Regression tests verify TSLA→TSLA and SPY↔VOO ETF-pair behavior is unchanged.
"""
from datetime import date
from decimal import Decimal

from net_alpha.engine.detector import detect_in_window, detect_wash_sales
from net_alpha.models.domain import OptionDetails, Trade


def _opt_loss(ticker: str, d: date, *, qty: float = 1, premium: Decimal = Decimal("100")) -> Trade:
    return Trade(
        id=f"{ticker}-loss-{d.isoformat()}",
        date=d,
        account="test/personal",
        ticker=ticker,
        action="sell",
        quantity=qty,
        proceeds=premium,
        cost_basis=premium + Decimal("621.50"),
        option_details=OptionDetails(strike=4500, expiry=date(2025, 12, 19), call_put="C"),
        is_section_1256=(ticker in {"SPX", "NDX", "RUT", "VIX", "OEX", "XSP"}),
    )


def _opt_buy(ticker: str, d: date, *, qty: float = 1, premium: Decimal = Decimal("100")) -> Trade:
    return Trade(
        id=f"{ticker}-buy-{d.isoformat()}",
        date=d,
        account="test/personal",
        ticker=ticker,
        action="buy",
        quantity=qty,
        proceeds=premium,
        cost_basis=premium,
        option_details=OptionDetails(strike=4500, expiry=date(2025, 12, 19), call_put="C"),
        is_section_1256=(ticker in {"SPX", "NDX", "RUT", "VIX", "OEX", "XSP"}),
    )


def _stock(ticker: str, action: str, d: date, *, qty: float = 100, basis: Decimal = Decimal("10000")) -> Trade:
    return Trade(
        id=f"{ticker}-{action}-{d.isoformat()}",
        date=d,
        account="test/personal",
        ticker=ticker,
        action=action,
        quantity=qty,
        proceeds=basis - Decimal("1243") if action == "sell" else basis,
        cost_basis=basis,
        option_details=None,
    )


def test_spx_to_spx_emits_exempt_match_not_violation():
    loss = _opt_loss("SPX", date(2024, 9, 15))
    buy = _opt_buy("SPX", date(2024, 9, 22))
    result = detect_wash_sales([buy, loss], etf_pairs={})
    assert result.violations == []
    assert len(result.exempt_matches) == 1
    em = result.exempt_matches[0]
    assert em.exempt_reason == "section_1256"
    assert em.rule_citation == "IRC §1256(c)"
    assert em.ticker == "SPX"
    assert em.notional_disallowed > Decimal("0")


def test_tsla_to_tsla_still_emits_violation():
    loss = _stock("TSLA", "sell", date(2024, 9, 15))
    buy = _stock("TSLA", "buy", date(2024, 9, 22), qty=50, basis=Decimal("5000"))
    result = detect_wash_sales([buy, loss], etf_pairs={})
    assert len(result.violations) == 1
    assert result.exempt_matches == []


def test_etf_pair_match_still_works():
    loss = _stock("SPY", "sell", date(2024, 9, 15))
    buy = _stock("VOO", "buy", date(2024, 9, 22), qty=100, basis=Decimal("9000"))
    result = detect_wash_sales([buy, loss], etf_pairs={"sp500": ["SPY", "VOO", "IVV"]})
    assert len(result.violations) == 1
    assert result.exempt_matches == []


def test_candidate_only_section_1256_still_emits_exempt():
    """Either side §1256 → exempt. This exercises the candidate-only arm of the
    `or`: same ticker on both sides (so the matcher links them), but is_section_1256
    is True only on the candidate buy.
    Note: cross-ticker mixed cases (e.g., SPY loss → SPX buy) are not reachable
    via the existing matcher (which doesn't link SPY and SPX), so we exercise the
    candidate-arm of the `or` via a same-ticker pair with asymmetric flags."""
    loss = _opt_loss("SPX", date(2024, 9, 15))
    loss = loss.model_copy(update={"is_section_1256": False})  # force loss flag off
    buy = _opt_buy("SPX", date(2024, 9, 22))  # buy still has is_section_1256=True
    assert loss.is_section_1256 is False
    assert buy.is_section_1256 is True
    result = detect_wash_sales([buy, loss], etf_pairs={})
    assert result.violations == []
    assert len(result.exempt_matches) == 1
    assert result.exempt_matches[0].exempt_reason == "section_1256"


def test_exempt_match_preserves_confidence():
    loss = _opt_loss("SPX", date(2024, 9, 15))
    buy = _opt_buy("SPX", date(2024, 9, 22))
    result = detect_wash_sales([buy, loss], etf_pairs={})
    assert result.exempt_matches[0].confidence in {"Confirmed", "Probable", "Unclear"}


def test_detect_in_window_includes_section_1256_exempt_inside_window():
    loss = _opt_loss("SPX", date(2024, 9, 15))
    buy = _opt_buy("SPX", date(2024, 9, 22))
    # Window covers both trades
    result = detect_in_window(
        [buy, loss],
        window_start=date(2024, 9, 1),
        window_end=date(2024, 9, 30),
        etf_pairs={},
    )
    assert len(result.exempt_matches) == 1
    assert result.exempt_matches[0].ticker == "SPX"


def test_detect_in_window_excludes_section_1256_exempt_outside_window():
    loss = _opt_loss("SPX", date(2024, 9, 15))
    buy = _opt_buy("SPX", date(2024, 9, 22))
    # Window does NOT include the trade dates
    result = detect_in_window(
        [buy, loss],
        window_start=date(2025, 1, 1),
        window_end=date(2025, 1, 31),
        etf_pairs={},
    )
    assert result.exempt_matches == []
