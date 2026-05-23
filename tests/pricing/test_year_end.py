from datetime import date, timedelta
from decimal import Decimal

from net_alpha.models.domain import OptionDetails
from net_alpha.pricing.year_end import (
    black_scholes,
    hist_vol_30d,
    last_business_day,
    year_end_fmv,
)


def test_last_business_day_2025():
    # Dec 31 2025 is a Wednesday
    assert last_business_day(2025) == date(2025, 12, 31)


def test_last_business_day_2022():
    # Dec 31 2022 was a Saturday → Friday Dec 30
    assert last_business_day(2022) == date(2022, 12, 30)


def test_last_business_day_2023():
    # Dec 31 2023 was a Sunday → Friday Dec 29
    assert last_business_day(2023) == date(2023, 12, 29)


def _nclose(a: Decimal, b: Decimal, tol: Decimal = Decimal("0.05")) -> bool:
    return abs(a - b) <= tol


def test_black_scholes_atm_call_30d():
    p = black_scholes(
        S=Decimal("100"),
        K=Decimal("100"),
        T=Decimal("30") / Decimal("365"),
        r=Decimal("0.05"),
        sigma=Decimal("0.20"),
        call_put="C",
    )
    assert _nclose(p, Decimal("2.51"))


def test_black_scholes_atm_put_30d():
    p = black_scholes(
        S=Decimal("100"),
        K=Decimal("100"),
        T=Decimal("30") / Decimal("365"),
        r=Decimal("0.05"),
        sigma=Decimal("0.20"),
        call_put="P",
    )
    assert _nclose(p, Decimal("2.10"))


def test_black_scholes_deep_itm_call_floor_intrinsic():
    import math as _m

    p = black_scholes(
        S=Decimal("150"),
        K=Decimal("100"),
        T=Decimal("30") / Decimal("365"),
        r=Decimal("0.05"),
        sigma=Decimal("0.20"),
        call_put="C",
    )
    discounted_intrinsic = Decimal("150") - Decimal("100") * Decimal(str(_m.exp(-0.05 * 30 / 365)))
    assert p >= discounted_intrinsic - Decimal("0.01")


def test_black_scholes_expired_returns_intrinsic():
    p = black_scholes(
        S=Decimal("100"),
        K=Decimal("90"),
        T=Decimal("0"),
        r=Decimal("0.05"),
        sigma=Decimal("0.20"),
        call_put="C",
    )
    assert p == Decimal("10")
    p2 = black_scholes(
        S=Decimal("100"),
        K=Decimal("110"),
        T=Decimal("0"),
        r=Decimal("0.05"),
        sigma=Decimal("0.20"),
        call_put="P",
    )
    assert p2 == Decimal("10")


def test_black_scholes_zero_vol():
    import math as _m

    p = black_scholes(
        S=Decimal("100"),
        K=Decimal("90"),
        T=Decimal("30") / Decimal("365"),
        r=Decimal("0.05"),
        sigma=Decimal("0"),
        call_put="C",
    )
    discounted_intrinsic = Decimal("100") - Decimal("90") * Decimal(str(_m.exp(-0.05 * 30 / 365)))
    assert _nclose(p, discounted_intrinsic, tol=Decimal("0.001"))


def test_hist_vol_30d_constant_returns_zero():
    closes = {date(2025, 11, 1) + timedelta(days=i): Decimal("100") for i in range(45)}
    v = hist_vol_30d(closes, date(2025, 12, 15))
    assert v is not None
    assert v == Decimal("0")


def test_hist_vol_30d_insufficient_data_returns_none():
    closes = {date(2025, 12, 14): Decimal("100"), date(2025, 12, 15): Decimal("101")}
    v = hist_vol_30d(closes, date(2025, 12, 15))
    assert v is None


def test_hist_vol_30d_known_series():
    closes = {}
    price = 100.0
    d = date(2025, 11, 1)
    for i in range(45):
        price = price * (1.01 if i % 2 == 0 else 1 / 1.01)
        closes[d] = Decimal(str(round(price, 6)))
        d = d + timedelta(days=1)
    v = hist_vol_30d(closes, date(2025, 12, 15))
    assert v is not None
    assert Decimal("0.10") < v < Decimal("0.30")


def test_hist_vol_30d_uses_calendar_day_annualizer():
    """Audit #10: hist_vol_30d must use sqrt(365) to match T = days/365.

    Build a deterministic series of daily log-returns alternating +0.01 / -0.01,
    so the daily stdev is exactly known. Verify the annualized value uses
    sqrt(365), not sqrt(252).
    """
    import math as _m

    closes: dict[date, Decimal] = {}
    d = date(2025, 11, 15)
    price = 100.0
    # 31 daily prices => 30 daily log returns, all within the 30-calendar-day window
    closes[d] = Decimal(str(round(price, 8)))
    for i in range(30):
        # alternating multiplicative factors give log returns of +ln(1.01) / -ln(1.01)
        price = price * (1.01 if i % 2 == 0 else 1 / 1.01)
        d = d + timedelta(days=1)
        closes[d] = Decimal(str(round(price, 8)))

    anchor = max(closes)
    v = hist_vol_30d(closes, anchor)
    assert v is not None

    # The known per-day stdev (population-free, sample stdev with ddof=1) of the
    # alternating series equals sqrt(sum((r-mean)^2)/(n-1)).
    log_returns = []
    sorted_d = sorted(closes)
    for i in range(1, len(sorted_d)):
        log_returns.append(_m.log(float(closes[sorted_d[i]]) / float(closes[sorted_d[i - 1]])))
    mean = sum(log_returns) / len(log_returns)
    variance = sum((r - mean) ** 2 for r in log_returns) / (len(log_returns) - 1)
    daily_stdev = _m.sqrt(variance)
    expected_calendar = Decimal(str(round(daily_stdev * _m.sqrt(365), 6)))
    expected_trading = Decimal(str(round(daily_stdev * _m.sqrt(252), 6)))

    # The calendar-day convention must be picked; reject the trading-day annualizer.
    assert abs(v - expected_calendar) <= Decimal("0.0001"), (
        f"Expected calendar-day annualizer (~{expected_calendar}), got {v}"
    )
    assert abs(v - expected_trading) > Decimal("0.01"), (
        "hist_vol_30d still using trading-day sqrt(252); expected sqrt(365)"
    )


def test_black_scholes_atm_call_30d_hull_textbook_value():
    """Audit #10: with consistent calendar-day convention, a 30-calendar-day ATM
    call at S=K=100, r=0.05, sigma=0.20 should price near the Hull-textbook
    closed-form (~$2.51) — the same as the existing
    test_black_scholes_atm_call_30d. This test re-asserts it to guard the
    convention boundary between hist_vol_30d and black_scholes."""
    p = black_scholes(
        S=Decimal("100"),
        K=Decimal("100"),
        T=Decimal("30") / Decimal("365"),
        r=Decimal("0.05"),
        sigma=Decimal("0.20"),
        call_put="C",
    )
    assert _nclose(p, Decimal("2.51"), tol=Decimal("0.05"))


class _FakeProvider:
    def __init__(self, *, option_close=None, underlying_closes=None):
        self._option_close = option_close
        self._underlying_closes = underlying_closes or {}

    def get_historical_close(self, symbol, on):
        if "_OPT_" in symbol:
            return self._option_close
        return self._underlying_closes.get(on)

    def get_historical_closes(self, symbol, start, end):
        return {d: p for d, p in self._underlying_closes.items() if start <= d <= end}


def test_year_end_fmv_prefers_option_close():
    opt = OptionDetails(strike=4000.0, expiry=date(2026, 6, 19), call_put="C")
    prov = _FakeProvider(option_close=Decimal("125.50"))
    price, source = year_end_fmv(ticker="SPX", option_details=opt, year=2025, provider=prov)
    assert source == "yahoo_close"
    assert price == Decimal("125.50")


def test_year_end_fmv_falls_back_to_black_scholes():
    opt = OptionDetails(strike=100.0, expiry=date(2026, 1, 30), call_put="C")
    closes = {}
    d = date(2025, 11, 27)
    while d <= date(2025, 12, 31):
        closes[d] = Decimal("100")
        d = d + timedelta(days=1)
    prov = _FakeProvider(option_close=None, underlying_closes=closes)
    price, source = year_end_fmv(ticker="SPX", option_details=opt, year=2025, provider=prov)
    assert source == "black_scholes"
    assert price >= Decimal("0")


def test_year_end_fmv_expired_returns_intrinsic():
    opt = OptionDetails(strike=90.0, expiry=date(2025, 11, 21), call_put="C")
    closes = {date(2025, 11, 21): Decimal("105")}
    prov = _FakeProvider(option_close=None, underlying_closes=closes)
    price, source = year_end_fmv(ticker="SPX", option_details=opt, year=2025, provider=prov)
    assert source == "intrinsic"
    assert price == Decimal("15")


def test_year_end_fmv_missing_all_sources():
    opt = OptionDetails(strike=4000.0, expiry=date(2026, 6, 19), call_put="C")
    prov = _FakeProvider(option_close=None, underlying_closes={})
    price, source = year_end_fmv(ticker="SPX", option_details=opt, year=2025, provider=prov)
    assert source == "missing"
    assert price is None
