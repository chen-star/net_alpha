from __future__ import annotations

from datetime import date, timedelta

from rich.console import Console

from net_alpha.cli.output import confidence_style, format_currency, print_disclaimer

console = Console()


def status_command() -> None:
    """Show imported data freshness, last scan results, and open rebuy windows."""
    from net_alpha.cli.app import _bootstrap
    from net_alpha.db.repository import MetaRepository, TradeRepository, ViolationRepository

    settings, session = _bootstrap()
    trade_repo = TradeRepository(session)
    violation_repo = ViolationRepository(session)
    meta_repo = MetaRepository(session)

    all_trades = trade_repo.list_all()
    if not all_trades:
        console.print("\n  No trades imported. Run [bold]net-alpha import[/bold] to get started.")
        session.close()
        return

    accounts = trade_repo.list_accounts()

    # Data freshness
    console.print()
    console.print("  [bold]DATA FRESHNESS[/bold]")
    console.print("  " + "\u2500" * 50)
    for account in sorted(accounts):
        count = trade_repo.count_by_account(account)
        latest = trade_repo.latest_trade_date_by_account(account)
        days_str = _days_ago_str(latest) if latest else "unknown"
        style = _staleness_style(latest) if latest else "yellow"
        stale_marker = "  [yellow]\u26a0[/yellow]" if style == "yellow" else ""
        console.print(f"  {account:<20} {count:>5} trades    last import: {latest}  ({days_str}){stale_marker}")

    # Violation summary
    violations = violation_repo.list_all()
    last_check = meta_repo.get("last_check_at")
    scan_year = date.today().year

    console.print()
    check_label = f"last check: {last_check}" if last_check else "never scanned"
    console.print(f"  [bold]WASH SALE SUMMARY \u2014 {scan_year} ({check_label})[/bold]")
    console.print("  " + "\u2500" * 50)

    if not violations:
        console.print("  No scan results yet. Run [bold]net-alpha check[/bold].")
    else:
        trade_repo_map = {t.id: t for t in all_trades}
        year_violations = [v for v in violations if trade_repo_map[v.loss_trade_id].date.year == scan_year]
        total = 0.0
        for label in ("Confirmed", "Probable", "Unclear"):
            vs = [v for v in year_violations if v.confidence == label]
            if vs:
                amt = sum(v.disallowed_loss for v in vs)
                total += amt
                style = confidence_style(label)
                console.print(
                    f"  [{style}]{label:12s}[/{style}] "
                    f"{len(vs):>3d} violations    "
                    f"{format_currency(amt):>12s} disallowed"
                )
        console.print("  " + "\u2500" * 50)
        console.print(f"  Total disallowed loss:       {format_currency(total)}")

    # Open rebuy windows
    rebuy_count = _count_open_rebuy_windows(all_trades, violations)
    if rebuy_count > 0:
        console.print()
        console.print("  [bold]OPEN REBUY WINDOWS[/bold]")
        console.print("  " + "\u2500" * 50)
        console.print(f"  {rebuy_count} position(s) still in 30-day window \u2014 run [bold]net-alpha rebuys[/bold]")

    console.print()
    console.print("  " + "\u2500" * 50)
    console.print("  Run [bold]net-alpha check[/bold] to re-scan with latest data.")

    print_disclaimer(console)
    session.close()


def _days_ago_str(date_str: str) -> str:
    """Return human-readable relative date string."""
    delta = (date.today() - date.fromisoformat(date_str)).days
    if delta == 0:
        return "today"
    if delta == 1:
        return "1 day ago"
    return f"{delta} days ago"


def _staleness_style(date_str: str) -> str:
    """Return 'yellow' if date is more than 30 days ago, else ''."""
    delta = (date.today() - date.fromisoformat(date_str)).days
    return "yellow" if delta > 30 else ""


def _count_open_rebuy_windows(all_trades: list, violations: list) -> int:
    """Count loss sales with open 30-day rebuy windows not fully matched."""
    today = date.today()
    matched_qty_by_loss: dict[str, float] = {}
    for v in violations:
        matched_qty_by_loss.setdefault(v.loss_trade_id, 0.0)
        matched_qty_by_loss[v.loss_trade_id] += v.matched_quantity

    count = 0
    for t in all_trades:
        if not t.is_loss():
            continue
        window_end = t.date + timedelta(days=30)
        if window_end < today:
            continue
        remaining = t.quantity - matched_qty_by_loss.get(t.id, 0.0)
        if remaining > 0:
            count += 1
    return count
