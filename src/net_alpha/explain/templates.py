"""Plain-English string builders for the P explanation surface.

These are the only place where rule citations and match-reason copy live.
Tests in tests/explain/test_templates.py pin the wording.
"""

from __future__ import annotations

from decimal import Decimal

_RULE_CITATIONS = {
    "regular": "IRC §1091(a) — Pub 550 p.59",
    "section_1256": "IRC §1256(c)",
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
