def render(violations) -> str:
    if not violations:
        return "(no violations)"
    lines = ["DETAIL — per-violation breakdown", "─" * 32]
    for v in violations:
        lines.append(
            f"{v.loss_sale_date} loss in {v.loss_account} → buy in {v.buy_account} "
            f"on {v.triggering_buy_date}: ${v.disallowed_loss:,.0f} disallowed "
            f"({v.matched_quantity} units, {v.confidence})"
        )
    return "\n".join(lines)
