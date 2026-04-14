from __future__ import annotations

from datetime import date, timedelta

from rich.console import Console
from rich.table import Table

from net_alpha.cli.output import print_disclaimer

console = Console()


def rebuys_command() -> None:
    """Show positions in wash sale window safe to rebuy after waiting period."""
    from net_alpha.cli.app import _bootstrap
    from net_alpha.db.repository import TradeRepository, ViolationRepository

    settings, session = _bootstrap()
    trade_repo = TradeRepository(session)
    violation_repo = ViolationRepository(session)

    all_trades = trade_repo.list_all()
    violations = violation_repo.list_all()

    today = date.today()

    # Track partial matches: how much of each loss sale is already matched
    matched_qty_by_loss = {}
    for v in violations:
        matched_qty_by_loss.setdefault(v.loss_trade_id, 0.0)
        matched_qty_by_loss[v.loss_trade_id] += v.matched_quantity

    rebuy_entries = []
    for t in all_trades:
        if not t.is_loss():
            continue
        window_end = t.date + timedelta(days=30)
        if window_end < today:
            continue  # Window already closed

        matched = matched_qty_by_loss.get(t.id, 0.0)
        remaining = t.quantity - matched
        if remaining <= 0:
            continue  # Fully matched — no open quantity

        days_remaining = (window_end - today).days
        qty_display = f"{remaining:.0f}/{t.quantity:.0f}" if matched > 0 else f"{t.quantity:.0f}"
        rebuy_entries.append(
            {
                "ticker": t.ticker,
                "qty_display": qty_display,
                "sold_date": t.date,
                "account": t.account,
                "safe_date": window_end,
                "days_remaining": days_remaining,
            }
        )

    if not rebuy_entries:
        console.print("\n  No positions currently in wash sale window. All clear.")
        print_disclaimer(console)
        session.close()
        return

    console.print()
    console.print("  [bold]SAFE-TO-REBUY TRACKER[/bold]")

    table = Table(box=None, padding=(0, 2), show_edge=False)
    table.add_column("Ticker")
    table.add_column("Qty Open")
    table.add_column("Sold Date")
    table.add_column("Account")
    table.add_column("Safe to Rebuy")
    table.add_column("Days Remaining", justify="right")

    for entry in sorted(rebuy_entries, key=lambda e: e["safe_date"]):
        table.add_row(
            entry["ticker"],
            entry["qty_display"],
            str(entry["sold_date"]),
            entry["account"],
            str(entry["safe_date"]),
            f"{entry['days_remaining']} days",
        )

    console.print(table)
    console.print(f"\n  {len(rebuy_entries)} positions in wash sale window.")

    print_disclaimer(console)
    session.close()
