"""Year-end FMV for §1256 mark-to-market — three-step cascade."""

from __future__ import annotations

import math
from datetime import date, timedelta
from decimal import Decimal


def last_business_day(year: int) -> date:
    """Last business day of `year` — Dec 31 if M-F, otherwise prior Friday."""
    d = date(year, 12, 31)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _phi(x: float) -> float:
    """Standard normal CDF."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def black_scholes(
    *,
    S: Decimal,
    K: Decimal,
    T: Decimal,
    r: Decimal,
    sigma: Decimal,
    call_put: str,
) -> Decimal:
    """European Black-Scholes price (call or put); returns a non-negative Decimal."""
    cp = call_put.upper()
    if cp not in ("C", "P"):
        raise ValueError(f"call_put must be 'C' or 'P', got {call_put!r}")

    Sf, Kf, Tf, rf, sf = float(S), float(K), float(T), float(r), float(sigma)
    if Tf <= 0 or sf <= 0:
        if cp == "C":
            intrinsic = max(0.0, Sf - Kf * math.exp(-rf * max(Tf, 0.0)))
        else:
            intrinsic = max(0.0, Kf * math.exp(-rf * max(Tf, 0.0)) - Sf)
        return Decimal(str(round(intrinsic, 6)))

    d1 = (math.log(Sf / Kf) + (rf + 0.5 * sf * sf) * Tf) / (sf * math.sqrt(Tf))
    d2 = d1 - sf * math.sqrt(Tf)

    if cp == "C":
        price = Sf * _phi(d1) - Kf * math.exp(-rf * Tf) * _phi(d2)
    else:
        price = Kf * math.exp(-rf * Tf) * _phi(-d2) - Sf * _phi(-d1)

    return Decimal(str(round(max(price, 0.0), 6)))


def hist_vol_30d(closes: dict[date, Decimal], anchor: date) -> Decimal | None:
    """Annualized stdev of daily log-returns over 30 calendar days ending on `anchor` (inclusive)."""
    window_start = anchor - timedelta(days=30)
    in_window = sorted(d for d in closes if window_start <= d <= anchor)
    if len(in_window) < 5:
        return None

    prices = [float(closes[d]) for d in in_window]
    log_returns: list[float] = []
    for i in range(1, len(prices)):
        if prices[i - 1] <= 0 or prices[i] <= 0:
            continue
        log_returns.append(math.log(prices[i] / prices[i - 1]))
    if len(log_returns) < 2:
        return None

    mean = sum(log_returns) / len(log_returns)
    variance = sum((r - mean) ** 2 for r in log_returns) / (len(log_returns) - 1)
    daily_stdev = math.sqrt(variance)
    annualized = daily_stdev * math.sqrt(252)
    return Decimal(str(round(annualized, 6)))


def _option_symbol(ticker: str, opt) -> str:
    """Synthetic symbol the provider can intercept and route to its option-data feed."""
    return f"{ticker}_OPT_{opt.expiry.isoformat()}_{opt.strike}_{opt.call_put}"


def year_end_fmv(
    *,
    ticker: str,
    option_details,
    year: int,
    provider,
    risk_free_rate: Decimal = Decimal("0.045"),
) -> tuple[Decimal | None, str]:
    """Three-step FMV cascade: option close → Black-Scholes → intrinsic."""
    if option_details is None:
        return None, "missing"

    lbd = last_business_day(year)

    sym = _option_symbol(ticker, option_details)
    option_close = provider.get_historical_close(sym, lbd)
    if option_close is not None and option_close > 0:
        return option_close, "yahoo_close"

    if option_details.expiry < lbd:
        underlying_at_expiry = provider.get_historical_close(ticker, option_details.expiry)
        if underlying_at_expiry is None:
            return None, "missing"
        K = Decimal(str(option_details.strike))
        if option_details.call_put.upper() == "C":
            return max(Decimal("0"), underlying_at_expiry - K), "intrinsic"
        return max(Decimal("0"), K - underlying_at_expiry), "intrinsic"

    closes = provider.get_historical_closes(ticker, lbd - timedelta(days=45), lbd)
    if not closes:
        return None, "missing"
    S = closes.get(lbd)
    if S is None:
        prior = sorted(d for d in closes if d <= lbd)
        if not prior:
            return None, "missing"
        S = closes[prior[-1]]

    sigma = hist_vol_30d(closes, lbd)
    if sigma is None:
        K = Decimal(str(option_details.strike))
        if option_details.call_put.upper() == "C":
            return max(Decimal("0"), S - K), "intrinsic"
        return max(Decimal("0"), K - S), "intrinsic"

    days_to_expiry = (option_details.expiry - lbd).days
    T = Decimal(str(days_to_expiry)) / Decimal("365")
    price = black_scholes(
        S=S,
        K=Decimal(str(option_details.strike)),
        T=T,
        r=risk_free_rate,
        sigma=sigma,
        call_put=option_details.call_put,
    )
    return price, "black_scholes"
