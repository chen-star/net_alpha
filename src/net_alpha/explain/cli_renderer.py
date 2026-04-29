"""CLI --detail formatter: renders an ExplanationModel as a multi-line ASCII block.
Mirrors the visual structure of _violation_explain.html for parity."""
from __future__ import annotations

from net_alpha.explain.violation import ExplanationModel


def render_explanation(e: ExplanationModel) -> str:
    """Return a printable multi-line block describing the explanation."""
    lines: list[str] = []
    bar = "─" * 60

    lines.append(bar)
    lines.append(e.summary)
    lines.append(bar)

    lines.append(f"  Rule: {e.rule_citation}")
    lines.append(f"  Match: {e.match_reason}")
    lines.append(f"  Window: {e.days_between} days between sale and rebuy")

    lines.append("")
    lines.append("  Loss sale:")
    _trade_block(lines, e.loss_trade, indent="    ")
    lines.append("  Triggering buy:")
    _trade_block(lines, e.triggering_buy, indent="    ")

    lines.append("")
    if e.is_exempt:
        lines.append(f"  Would have disallowed: {e.disallowed_math}  →  $0 (exempt)")
    else:
        lines.append(f"  Disallowed: {e.disallowed_math}")

    lines.append(f"  Confidence: {e.confidence_reason}")

    if e.adjusted_basis_target is not None:
        a = e.adjusted_basis_target
        lines.append(f"  Rolled into: Lot {a.lot_id} ({a.acquired_date}) — adjusted basis ${a.adjusted_basis}")

    if e.cross_account is not None:
        lines.append(f"  Cross-account: {e.cross_account.loss_account} → {e.cross_account.buy_account}")

    if e.is_exempt:
        lines.append("  Reference: section_1256_underlyings.yaml")

    return "\n".join(lines)


def _trade_block(lines: list[str], t, *, indent: str) -> None:
    lines.append(f"{indent}{t.ticker}  {t.action} {t.quantity}  {t.date}")
    lines.append(f"{indent}proceeds ${t.proceeds}  basis ${t.cost_basis}")
