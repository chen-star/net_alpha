from __future__ import annotations

from datetime import date, timedelta


def render(lots, violations, today: date) -> str:
    lines = ["WATCH LIST — active rebuy windows", "─" * 33]
    if not violations and not lots:
        lines.append("(no active violations or open lots)")
        return "\n".join(lines)

    for v in violations:
        if v.triggering_buy_date and v.triggering_buy_date >= today - timedelta(days=30):
            ticker = _ticker_for_violation(v)
            lines.append(
                f"🔴 {ticker}   wash sale TRIGGERED on {v.loss_sale_date} "
                f"({ticker} buy on {v.triggering_buy_date})"
            )
            lines.append(
                f"          ${v.disallowed_loss:,.0f} loss disallowed → rolled into "
                f"{v.triggering_buy_date} lot"
            )
    return "\n".join(lines)


def _ticker_for_violation(v) -> str:
    """v2.0 placeholder — violations don't carry the ticker directly.
    Future enhancement: caller can join through trade rows and pass it in.
    """
    return "TKR"
