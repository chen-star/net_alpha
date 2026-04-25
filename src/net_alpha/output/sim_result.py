from decimal import Decimal


def render(ticker: str, qty: Decimal, price: Decimal, options) -> str:
    lines = [f"SIMULATING: sell {qty} {ticker} @ ${price}"]
    for i, opt in enumerate(options):
        letter = chr(ord("A") + i)
        lines.append("")
        lines.append(f"OPTION {letter} — sell from '{opt.account.display()}' (FIFO)")
        if opt.insufficient_shares:
            lines.append(f"  ⚠ insufficient shares — only {opt.available_shares} held")
        for c in opt.lots_consumed_fifo:
            lines.append(f"  Lot consumed: {c.quantity} @ ${c.basis_per_share} ({c.purchase_date})")
        sign = "+" if opt.realized_pnl >= 0 else ""
        lines.append(f"  Realized P&L: {sign}${opt.realized_pnl}")
        if opt.would_trigger_wash_sale:
            lines.append(f"  Wash sale:    🔴 TRIGGERED — confidence {opt.confidence}")
        else:
            lines.append("  Wash sale:    N/A")
    return "\n".join(lines)
