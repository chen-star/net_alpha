"""Plain-English string builders for the P explanation surface.

These are the only place where rule citations and match-reason copy live.
Tests in tests/explain/test_templates.py pin the wording.
"""

from __future__ import annotations

from decimal import Decimal

from net_alpha.models.domain import Trade


def classify_branch(loss: Trade, buy: Trade) -> str:
    """Fine-grained branch_kind matching engine.matcher.get_match_confidence.

    Returns one of:
      equity_equity, option_option_exact, option_option_partial,
      equity_to_call, option_to_equity, etf_pair, equity_to_sold_put, unknown.

    Pure: uses only ticker / action / option_details on the Trade objects.
    """
    # Different tickers — only ETF-pair detection lives in the engine; here we
    # trust the engine already classified the match and just report the shape.
    if loss.ticker != buy.ticker:
        return "etf_pair"

    loss_opt = loss.is_option()
    buy_opt = buy.is_option()

    # Equity loss / sold put on same ticker
    if not loss_opt and buy_opt and buy.is_sell() and buy.option_details.call_put == "P":
        return "equity_to_sold_put"

    # All other branches require buy.is_buy()
    if not buy.is_buy():
        return "unknown"

    # Both equities
    if not loss_opt and not buy_opt:
        return "equity_equity"

    # Equity loss / call buy
    if not loss_opt and buy_opt and buy.option_details.call_put == "C":
        return "equity_to_call"

    # Option loss / equity buy
    if loss_opt and not buy_opt:
        return "option_to_equity"

    # Both options on same underlying
    if loss_opt and buy_opt:
        if (
            loss.option_details.strike == buy.option_details.strike
            and loss.option_details.expiry == buy.option_details.expiry
            and loss.option_details.call_put == buy.option_details.call_put
        ):
            return "option_option_exact"
        return "option_option_partial"

    return "unknown"


_RULE_CITATIONS = {
    "regular": "IRC §1091(a) — Pub 550 p.59",
    "section_1256": "IRC §1256(c)",
    "permanent_ira": "IRC §1091(a) + Rev. Rul. 2008-5 — basis rollover blocked (IRA)",
}


def rule_citation(reason: str) -> str:
    """Return the canonical rule citation string for *reason*.
    Falls back to "regular" for unknown reasons (defensive)."""
    return _RULE_CITATIONS.get(reason, _RULE_CITATIONS["regular"])


def match_reason_text(
    *,
    match_kind: str,
    loss_ticker: str,
    buy_ticker: str,
    group: str | None = None,
    option_details: str | None = None,
) -> str:
    """Plain-English match reason. *match_kind* ∈ {"exact_ticker", "etf_pair", "option_chain"}."""
    if match_kind == "exact_ticker":
        return f"exact ticker — {loss_ticker}"
    if match_kind == "etf_pair":
        return f"ETF pair: {loss_ticker} ↔ {buy_ticker} (group={group}, etf_pairs.yaml)"
    if match_kind == "option_chain":
        return f"option chain: {option_details}"
    return f"{loss_ticker} → {buy_ticker}"


def disallowed_math_str(*, loss: Decimal, allocable_qty: float, loss_qty: float) -> str:
    """Render the disallowed-amount math as a string.
    Full match: '$1,243.00'.
    Partial match: '$1,243.00 × (50 / 100) = $621.50'."""
    loss_fmt = f"${_fmt(loss)}"
    if allocable_qty == loss_qty:
        return loss_fmt
    disallowed = (loss * Decimal(str(allocable_qty)) / Decimal(str(loss_qty))).quantize(Decimal("0.01"))
    return f"{loss_fmt} × ({_fmt_qty(allocable_qty)} / {_fmt_qty(loss_qty)}) = ${_fmt(disallowed)}"


def confidence_reason(label: str, *, match_kind: str, days_between: int) -> str:
    """One-sentence rationale for the confidence label."""
    base = f"{label} — "
    if match_kind == "exact_ticker":
        kind = "exact ticker match"
    elif match_kind == "etf_pair":
        kind = "ETF substantially-identical pair"
    elif match_kind == "option_chain":
        kind = "option chain match"
    else:
        kind = "ticker match"
    return f"{base}{kind} within {days_between} days"


# ---- formatting helpers ---------------------------------------------------


def _fmt(d: Decimal) -> str:
    """Render Decimal with thousand-separators and 2dp."""
    sign = "-" if d < 0 else ""
    abs_d = abs(d).quantize(Decimal("0.01"))
    int_part, _, dec_part = f"{abs_d}".partition(".")
    int_with_commas = f"{int(int_part):,}"
    return f"{sign}{int_with_commas}.{dec_part or '00'}"


def _fmt_qty(q: float) -> str:
    """Whole quantity → integer string; fractional → up to 4dp."""
    if q == int(q):
        return str(int(q))
    return f"{q:.4f}".rstrip("0").rstrip(".")


_CONFIDENCE_DELTA: dict[str, tuple[str | None, str | None]] = {
    "equity_equity": (
        None,
        "Would be Probable if the replacement were a call option on the same "
        "ticker, or Unclear if it were a substantially-identical ETF "
        "(e.g. SPY ↔ VOO).",
    ),
    "option_option_exact": (
        None,
        "Would be Probable if any of strike, expiry, or call/put differed from the loss contract.",
    ),
    "option_option_partial": (
        "Would be Confirmed if strike, expiry, and call/put all matched the loss contract.",
        None,
    ),
    "equity_to_call": (
        "Would be Confirmed if the replacement were the underlying equity rather than a call option.",
        None,
    ),
    "option_to_equity": (
        "Would be Confirmed if the replacement were the same option contract rather than the underlying equity.",
        None,
    ),
    "etf_pair": (
        "Would be Confirmed if the replacement were the same ETF ticker as "
        "the loss, or Probable if it were a call option on the loss ETF.",
        None,
    ),
    "equity_to_sold_put": (
        "Would be Probable if the replacement were a call on the same "
        "ticker, or Confirmed if you bought the underlying equity.",
        None,
    ),
}


def confidence_delta(branch_kind: str) -> tuple[str | None, str | None]:
    """Return (promote_hint, demote_hint) for a branch_kind.

    Unknown branch_kinds return (None, None) defensively.
    """
    return _CONFIDENCE_DELTA.get(branch_kind, (None, None))
