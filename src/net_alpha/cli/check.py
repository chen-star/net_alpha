from __future__ import annotations

from datetime import date, timedelta

import typer
from rich.console import Console
from rich.table import Table

from net_alpha.cli.output import (
    confidence_style,
    format_currency,
    print_disclaimer,
)

console = Console()


def check_command(
    ticker: str | None = typer.Option(None, help="Filter by ticker"),
    type: str | None = typer.Option(None, help="Filter by type: equities, options"),
    year: int | None = typer.Option(None, help="Tax year (default: current)"),
) -> None:
    """Scan all trades for wash sale violations."""

    from net_alpha.cli.app import _bootstrap
    from net_alpha.db.repository import (
        LotRepository,
        TradeRepository,
        ViolationRepository,
    )
    from net_alpha.engine.detector import detect_wash_sales
    from net_alpha.engine.etf_pairs import load_etf_pairs

    settings, session = _bootstrap()
    trade_repo = TradeRepository(session)
    violation_repo = ViolationRepository(session)
    lot_repo = LotRepository(session)

    all_trades = trade_repo.list_all()
    if not all_trades:
        console.print("  No trades imported yet. Run [bold]net-alpha import[/bold] first.")
        session.close()
        return

    # Load ETF pairs
    etf_path = settings.user_etf_pairs_path
    user_pairs = etf_path if etf_path.exists() else None
    etf_pairs = load_etf_pairs(user_pairs_path=user_pairs)

    # Run detection
    with console.status("Scanning for wash sales\u2026", spinner="dots"):
        result = detect_wash_sales(all_trades, etf_pairs)

    # Persist results (clear old, write new)
    violation_repo.delete_all()
    lot_repo.delete_all()
    violation_repo.save_batch(result.violations)
    lot_repo.save_batch(result.lots)
    session.commit()

    # Build trade lookup
    trade_map = {t.id: t for t in all_trades}

    # Filter by year
    scan_year = year or date.today().year
    violations = _filter_violations_by_year(result.violations, trade_map, scan_year)

    # Filter by ticker
    if ticker:
        violations = [v for v in violations if trade_map[v.loss_trade_id].ticker == ticker.upper()]

    # Filter by type
    if type:
        if type.lower() == "options":
            violations = [v for v in violations if trade_map[v.loss_trade_id].is_option()]
        elif type.lower() == "equities":
            violations = [v for v in violations if not trade_map[v.loss_trade_id].is_option()]

    # Staleness warning
    _print_staleness_warnings(trade_repo, console)

    # Print summary
    _print_summary(violations, scan_year, console)

    # Print detail table
    if violations:
        _print_detail_table(violations, trade_map, console)

    # Rebuy hint
    rebuy_count = _count_rebuys(all_trades, result.violations, trade_map)
    if rebuy_count > 0:
        console.print(f"\n  {rebuy_count} positions safe to rebuy — run [bold]net-alpha rebuys[/bold] for details")

    # Basis unknown warning
    if result.basis_unknown_count > 0:
        console.print(
            f"\n  [yellow]{result.basis_unknown_count} trades have no cost basis — "
            "disallowed loss amounts may be incomplete.[/yellow]"
        )

    # Option expiration warning
    if any(t.is_option() for t in all_trades):
        console.print(
            "\n  [dim]Note: option expirations missing from your broker CSV "
            "(e.g. Robinhood) will not appear as loss sales — wash sale "
            "exposure from expired options may be undetected.[/dim]"
        )

    print_disclaimer(console)
    session.close()


def _filter_violations_by_year(violations: list, trade_map: dict, year: int) -> list:
    """Filter violations to those whose loss sale occurred in the given year."""
    return [v for v in violations if trade_map[v.loss_trade_id].date.year == year]


def _build_summary(violations: list) -> dict:
    """Build count and total by confidence label."""
    summary = {
        "Confirmed": {"count": 0, "total": 0.0},
        "Probable": {"count": 0, "total": 0.0},
        "Unclear": {"count": 0, "total": 0.0},
    }
    for v in violations:
        if v.confidence in summary:
            summary[v.confidence]["count"] += 1
            summary[v.confidence]["total"] += v.disallowed_loss
    return summary


def _print_summary(violations: list, year: int, console: Console) -> None:
    summary = _build_summary(violations)
    total = sum(s["total"] for s in summary.values())

    console.print()
    console.print(f"  [bold]WASH SALE SUMMARY — {year} (all accounts)[/bold]")
    console.print("  " + "\u2500" * 50)

    for label in ("Confirmed", "Probable", "Unclear"):
        s = summary[label]
        if s["count"] > 0:
            style = confidence_style(label)
            note = "  (recommend CPA review)" if label != "Confirmed" else ""
            console.print(
                f"  [{style}]{label:12s}[/{style}] "
                f"{s['count']:>3d} violations    "
                f"{format_currency(s['total']):>12s} disallowed{note}"
            )

    console.print("  " + "\u2500" * 50)
    console.print(f"  Total disallowed loss:       {format_currency(total)}")


def _print_detail_table(violations: list, trade_map: dict, console: Console) -> None:
    console.print()
    console.print("  [bold]DETAIL[/bold]")

    table = Table(box=None, padding=(0, 2), show_edge=False)
    table.add_column("Date")
    table.add_column("Ticker")
    table.add_column("Account")
    table.add_column("Type")
    table.add_column("Loss", justify="right")
    table.add_column("Status")
    table.add_column("Disallowed", justify="right")

    for v in sorted(violations, key=lambda x: trade_map[x.loss_trade_id].date):
        loss_trade = trade_map[v.loss_trade_id]
        trade_type = "Option" if loss_trade.is_option() else "Equity"
        style = confidence_style(v.confidence)
        table.add_row(
            str(loss_trade.date),
            loss_trade.ticker,
            loss_trade.account,
            trade_type,
            format_currency(-loss_trade.loss_amount()),
            f"[{style}]{v.confidence}[/{style}]",
            format_currency(v.disallowed_loss),
        )

    console.print(table)


def _print_staleness_warnings(trade_repo, console: Console) -> None:
    """Warn if any account's latest trade is older than 30 days."""
    accounts = trade_repo.list_accounts()
    today = date.today()

    for account in accounts:
        latest = trade_repo.latest_trade_date_by_account(account)
        if latest:
            from datetime import date as date_type

            latest_date = date_type.fromisoformat(latest)
            days_ago = (today - latest_date).days
            if days_ago > 30:
                console.print(
                    f"\n  [yellow]\u26a0 {account} data last imported "
                    f"{days_ago} days ago.[/yellow]"
                    f"\n    Run [bold]net-alpha import "
                    f"{account.lower()} <file>[/bold] to update."
                )


def _count_rebuys(all_trades: list, violations: list, trade_map: dict) -> int:
    """Count loss sales with open rebuy windows (no triggering buy detected yet)."""
    today = date.today()
    matched_loss_ids = {v.loss_trade_id for v in violations}
    count = 0
    for t in all_trades:
        if t.is_loss() and t.id not in matched_loss_ids:
            window_end = t.date + timedelta(days=30)
            if window_end >= today:
                count += 1
    return count
