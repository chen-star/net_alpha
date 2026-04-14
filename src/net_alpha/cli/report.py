from __future__ import annotations

import csv as csv_module
from datetime import date
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from net_alpha.cli.output import (
    confidence_style,
    format_currency,
    print_disclaimer,
)

console = Console()


def report_command(
    year: int | None = typer.Option(None, help="Tax year (default: current)"),
    csv: bool = typer.Option(False, "--csv", help="Also export CSV to current directory"),
) -> None:
    """Generate a wash sale report for a tax year."""

    from net_alpha.cli.app import _bootstrap
    from net_alpha.db.repository import TradeRepository
    from net_alpha.engine.detector import detect_wash_sales
    from net_alpha.engine.etf_pairs import load_etf_pairs

    settings, session = _bootstrap()
    trade_repo = TradeRepository(session)

    all_trades = trade_repo.list_all()
    if not all_trades:
        console.print("  No trades imported yet.")
        session.close()
        return

    user_pairs = settings.user_etf_pairs_path if settings.user_etf_pairs_path.exists() else None
    etf_pairs = load_etf_pairs(user_pairs_path=user_pairs)

    # Run fresh detection
    result = detect_wash_sales(all_trades, etf_pairs)
    trade_map = {t.id: t for t in all_trades}

    report_year = year or date.today().year

    # Filter violations by year (loss sale year)
    violations = [v for v in result.violations if trade_map[v.loss_trade_id].date.year == report_year]

    # Summary stats
    total_trades = len(all_trades)
    loss_trades = sum(1 for t in all_trades if t.is_loss() and t.date.year == report_year)
    confirmed = sum(1 for v in violations if v.confidence == "Confirmed")
    probable = sum(1 for v in violations if v.confidence == "Probable")
    unclear = sum(1 for v in violations if v.confidence == "Unclear")
    total_disallowed = sum(v.disallowed_loss for v in violations)

    console.print()
    console.print(f"  [bold]WASH SALE REPORT — Tax Year {report_year}[/bold]")
    console.print("  " + "\u2500" * 50)
    console.print(f"  Total trades imported:     {total_trades:,}")
    console.print(f"  Loss trades:               {loss_trades}")
    console.print(
        f"  Wash sales identified:     {len(violations)}  "
        f"({confirmed} Confirmed, {probable} Probable, {unclear} Unclear)"
    )
    console.print(f"  Total disallowed loss:     {format_currency(total_disallowed)}")
    console.print(f"  Adjusted cost basis delta: +{format_currency(total_disallowed)} (rolled into replacement lots)")
    console.print()

    # Detail table
    if violations:
        table = Table(box=None, padding=(0, 2), show_edge=False)
        table.add_column("Date")
        table.add_column("Ticker")
        table.add_column("Account")
        table.add_column("Type")
        table.add_column("Loss", justify="right")
        table.add_column("Status")
        table.add_column("Disallowed", justify="right")
        table.add_column("Replacement")

        for v in sorted(violations, key=lambda x: trade_map[x.loss_trade_id].date):
            loss_trade = trade_map[v.loss_trade_id]
            repl_trade = trade_map.get(v.replacement_trade_id)
            trade_type = "Option" if loss_trade.is_option() else "Equity"
            style = confidence_style(v.confidence)
            repl_info = ""
            if repl_trade:
                repl_info = f"{repl_trade.date} {repl_trade.account}"

            table.add_row(
                str(loss_trade.date),
                loss_trade.ticker,
                loss_trade.account,
                trade_type,
                format_currency(-loss_trade.loss_amount()),
                f"[{style}]{v.confidence}[/{style}]",
                format_currency(v.disallowed_loss),
                repl_info,
            )

        console.print(table)

    console.print()
    console.print(
        "  [dim]* Replacement lot allocation uses FIFO ordering. Your tax preparer may use a different method.[/dim]"
    )

    # CSV export
    if csv:
        csv_path = Path.cwd() / f"wash_sale_report_{report_year}.csv"
        _write_csv(csv_path, violations, trade_map)
        console.print(f"\n  CSV exported to: {csv_path}")

    print_disclaimer(console)
    session.close()


def _write_csv(path: Path, violations: list, trade_map: dict) -> None:
    with open(path, "w", newline="") as f:
        writer = csv_module.writer(f)
        writer.writerow(
            [
                "Date",
                "Ticker",
                "Account",
                "Type",
                "Loss",
                "Confidence",
                "Disallowed",
                "Replacement Date",
                "Replacement Account",
            ]
        )
        for v in sorted(violations, key=lambda x: trade_map[x.loss_trade_id].date):
            loss_trade = trade_map[v.loss_trade_id]
            repl_trade = trade_map.get(v.replacement_trade_id)
            trade_type = "Option" if loss_trade.is_option() else "Equity"
            writer.writerow(
                [
                    str(loss_trade.date),
                    loss_trade.ticker,
                    loss_trade.account,
                    trade_type,
                    f"{-loss_trade.loss_amount():.2f}",
                    v.confidence,
                    f"{v.disallowed_loss:.2f}",
                    str(repl_trade.date) if repl_trade else "",
                    repl_trade.account if repl_trade else "",
                ]
            )
