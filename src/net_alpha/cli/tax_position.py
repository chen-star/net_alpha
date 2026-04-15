from __future__ import annotations

from datetime import date

import typer
from rich.console import Console
from rich.table import Table

from net_alpha.cli.output import format_currency, print_disclaimer
from net_alpha.models.domain import OpenLot, TaxPosition

console = Console()


def tax_position_command(
    year: int | None = typer.Option(None, help="Tax year (default: current)"),
) -> None:
    """Show YTD tax position and open lot holding periods."""
    scan_year = year or date.today().year

    tp, open_lots = _load_trades_and_compute(scan_year)

    _render_tax_position(tp)
    _render_open_lots(open_lots)

    if tp.basis_unknown_count > 0:
        console.print(f"\n  [yellow]{tp.basis_unknown_count} sell(s) excluded due to unknown cost basis.[/yellow]")

    print_disclaimer(console)


def _load_trades_and_compute(year: int) -> tuple[TaxPosition, list[OpenLot]]:
    """Load trades from DB, compute tax position and open lots."""
    from net_alpha.cli.app import _bootstrap
    from net_alpha.db.repository import TradeRepository
    from net_alpha.engine.tax_position import compute_tax_position, identify_open_lots

    settings, session = _bootstrap()
    trade_repo = TradeRepository(session)
    all_trades = trade_repo.list_all()

    if not all_trades:
        console.print("  No trades imported yet. Run [bold]net-alpha import[/bold] first.")
        session.close()
        raise typer.Exit()

    tp = compute_tax_position(all_trades, year=year)
    open_lots = identify_open_lots(all_trades, as_of=date.today())
    session.close()
    return tp, open_lots


def _render_tax_position(tp: TaxPosition) -> None:
    console.print()
    console.print(f"  [bold]TAX POSITION \u2014 {tp.year} (all accounts)[/bold]")
    console.print("  " + "\u2500" * 50)
    console.print(f"  Short-term gains:          {format_currency(tp.st_gains):>12s}")
    console.print(f"  Short-term losses:         {format_currency(tp.st_losses):>12s}")
    console.print(f"  Net short-term:            {format_currency(tp.net_st):>12s}   (taxed at ordinary income rates)")
    console.print()
    console.print(f"  Long-term gains:           {format_currency(tp.lt_gains):>12s}")
    console.print(f"  Long-term losses:          {format_currency(tp.lt_losses):>12s}")
    console.print(f"  Net long-term:             {format_currency(tp.net_lt):>12s}   (taxed at preferential rates)")
    console.print()
    console.print("  " + "\u2500" * 50)
    console.print(f"  Net capital gain:          {format_currency(tp.net_capital_gain):>12s}")

    if tp.net_st > 0:
        console.print(f"  Loss still needed to zero short-term:  {format_currency(tp.loss_needed_to_zero_st)}")

    if tp.carryforward > 0:
        console.print(f"  Loss carryforward (above $3,000 cap):  {format_currency(tp.carryforward)}")


def _render_open_lots(open_lots: list[OpenLot]) -> None:
    if not open_lots:
        return

    console.print()
    console.print("  [bold]OPEN LOTS \u2014 Holding Period Tracker[/bold]")
    console.print("  " + "\u2500" * 50)

    table = Table(box=None, padding=(0, 2), show_edge=False)
    table.add_column("Ticker")
    table.add_column("Account")
    table.add_column("Qty", justify="right")
    table.add_column("Adj.Basis/sh", justify="right")
    table.add_column("Held")
    table.add_column("Days to Long-Term")

    for lot in open_lots:
        basis_str = "Unknown" if lot.basis_unknown else format_currency(lot.adjusted_basis_per_share)
        held_str = f"{lot.days_held}d"

        if lot.days_to_long_term == 0:
            lt_str = "Long-term \u2713"
        else:
            lt_str = f"{lot.days_to_long_term} days"

        table.add_row(
            lot.ticker,
            lot.account,
            str(int(lot.quantity)),
            basis_str,
            held_str,
            lt_str,
        )

    console.print(table)
