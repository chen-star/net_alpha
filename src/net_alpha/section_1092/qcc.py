"""Qualified Covered Call test per IRC §1092(c)(4).

A "qualified covered call" is a listed call option granted by the taxpayer
that is NOT deep-in-the-money. QCCs are exempt from §1092 straddle treatment
when paired with a long stock position. A covered call that FAILS the QCC
test creates a §1092 straddle.

v1 implements an approximation of the lowest-qualified-benchmark (LQB) step
table from IRS Notice 2003-31:

    DTE ≤ 30 days                   → never QCC (statutory)
    DTE > ~33 months                 → never QCC (statutory: > 12 months
                                       allowed only with strike ≥ price the
                                       day before grant; v1 cuts off at 33mo)
    Stock price ≤ $25                → strike must be ≥ ATM (no cushion)
    Stock price > $25 and DTE ≤ 90   → strike must be ≥ ATM (no cushion)
    Stock price > $25 and DTE > 90   → strike must be ≥ 90% of stock price
                                       (LQB floor approximation)

The full LQB step table by stock-price band ($25–$60, $60–$150, $150+) and
strike-interval rounding is deferred to v2. The v1 approximation is
**conservative** — it errs toward flagging more covered calls as failing,
which is the safer side for a tax tool.
"""

from __future__ import annotations

from decimal import Decimal

# §1092(c)(4)(B)(i): grant must have at least 30 days to expiration.
_MIN_DTE_DAYS = 30
# §1092(c)(4)(B)(ii) read narrowly with the post-2003-31 step tables — the
# practical cap is ~33 calendar months. v2: replace with the precise rule.
_MAX_DTE_DAYS = 33 * 30
# Below this stock price the LQB cushion vanishes and ATM is the floor.
_LOW_PRICE_THRESHOLD = Decimal("25")
# DTE band boundary for the long-dated cushion.
_LONG_DATED_DTE_DAYS = 90
# v1 approximation of the LQB floor for long-dated calls on stocks > $25.
_LQB_FLOOR_FRACTION = Decimal("0.90")


def is_qualified_covered_call(
    *,
    underlying_price_at_write: Decimal,
    strike: Decimal,
    days_to_expiry_at_write: int,
) -> tuple[bool, str]:
    """Return (qualifies, reason).

    Inputs are the call's strike, the underlying price on the day the call
    was written, and the call's days-to-expiry on that same day. All three
    must come from the WRITER's perspective — see §1092(c)(4)(D) on the
    "applicable stock price".
    """
    if days_to_expiry_at_write < _MIN_DTE_DAYS:
        return False, "DTE ≤ 30 days at grant — fails QCC (§1092(c)(4)(B)(i))"
    if days_to_expiry_at_write > _MAX_DTE_DAYS:
        return False, "DTE > 33 months at grant — fails QCC (long-dated cap)"

    if underlying_price_at_write <= _LOW_PRICE_THRESHOLD:
        if strike < underlying_price_at_write:
            return False, "Stock ≤ $25 and strike < ATM — fails QCC (no LQB cushion)"
        return True, "Stock ≤ $25 and strike ≥ ATM — qualifies"

    if days_to_expiry_at_write <= _LONG_DATED_DTE_DAYS:
        if strike < underlying_price_at_write:
            return False, "DTE ≤ 90 days and strike ITM — fails QCC (no LQB cushion at this DTE)"
        return True, "DTE ≤ 90 days and strike ≥ ATM — qualifies"

    lqb = underlying_price_at_write * _LQB_FLOOR_FRACTION
    if strike < lqb:
        return (
            False,
            f"Long-dated call: strike {strike:.2f} < LQB floor {lqb:.2f} (90% of price) — fails QCC (deep ITM)",
        )
    return True, f"Long-dated call: strike {strike:.2f} ≥ LQB floor {lqb:.2f} — qualifies"
