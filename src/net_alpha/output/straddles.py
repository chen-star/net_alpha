"""Plain-text renderer for `net-alpha straddles`."""

from __future__ import annotations

from net_alpha.models.domain import HoldingPeriodSuspension, OffsettingGroup, OffsettingPosition


def _format_position(p: OffsettingPosition) -> str:
    if p.option_strike is not None and p.option_expiry is not None:
        return (
            f"{p.kind} {p.ticker} {p.option_strike} {p.option_call_put} "
            f"exp {p.option_expiry.isoformat()} qty {p.quantity}"
        )
    return f"{p.kind} {p.ticker} qty {p.quantity}"


def render_straddles(
    *,
    groups: list[OffsettingGroup],
    suspensions: list[HoldingPeriodSuspension],
    detail: bool,
) -> str:
    if not groups and not suspensions:
        return "No active §1092 straddles detected."

    lines: list[str] = []
    lines.append("§1092 STRADDLES")
    lines.append("=" * 60)

    if not groups:
        lines.append("No offsetting groups currently open.")
    else:
        for g in groups:
            lines.append(f"[{g.confidence}] {g.kind}  {g.ticker}  ({g.account})")
            if detail:
                lines.append(f"  Rule: {g.rule_citation}")
                lines.append(f"  Why: {g.reasoning}")
                for p in g.positions:
                    lines.append(f"    - {_format_position(p)} (opened {p.opened_at.isoformat()})")
                lines.append("")

    if suspensions:
        lines.append("")
        lines.append("HOLDING-PERIOD SUSPENSIONS (§1092(f))")
        lines.append("=" * 60)
        for s in suspensions:
            resumed = s.resumed_at.isoformat() if s.resumed_at else "still active"
            lines.append(
                f"  {s.ticker} ({s.account}) lot {s.lot_id}: suspended {s.suspended_at.isoformat()} "
                f"({resumed}) — offset by {s.offsetting_position_kind}"
            )

    return "\n".join(lines)
