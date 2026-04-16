from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from net_alpha.cli.output import print_disclaimer, print_hint
from net_alpha.import_.schema_detection import SchemaMapping

console = Console()


def import_command(
    broker: str = typer.Argument(help="Broker name (e.g., schwab, robinhood)"),
    file: Path = typer.Argument(help="Path to CSV file", exists=True, readable=True, resolve_path=True),
) -> None:
    """Import trades from a broker CSV file."""
    from anthropic import Anthropic

    from net_alpha.cli.app import _bootstrap
    from net_alpha.db.repository import SchemaCacheRepository, TradeRepository
    from net_alpha.import_.importer import ImportContext, run_import

    settings, session = _bootstrap()

    # Resolve API key
    api_key = settings.anthropic_api_key
    if not api_key:
        console.print(
            "  [red]Error:[/red] ANTHROPIC_API_KEY not set. "
            "Set it via environment variable or in ~/.net_alpha/config.toml"
        )
        raise typer.Exit(1)

    client = Anthropic(api_key=api_key)

    ctx = ImportContext(
        csv_path=file,
        broker_name=broker.lower(),
        anthropic_client=client,
        model=settings.anthropic_model,
        max_retries=settings.llm_max_retries,
        confirm_schema=_confirm_schema,
        trade_repo=TradeRepository(session),
        schema_cache_repo=SchemaCacheRepository(session),
        session=session,
    )

    try:
        with console.status("Importing trades\u2026", spinner="dots"):
            result = run_import(ctx)
    except RuntimeError as e:
        console.print(f"  [red]Error:[/red] {e}")
        raise typer.Exit(1)
    finally:
        session.close()

    # Display results
    console.print()
    console.print(
        f"  Imported [bold]{result.new_imported}[/bold] trades from "
        f"[bold]{broker}[/bold] "
        f"({result.equities} equities, {result.options} options)"
    )
    if result.duplicates_skipped > 0:
        console.print(f"  {result.duplicates_skipped} duplicate trades skipped.")

    print_hint(console, "Run net-alpha check to scan for wash sales with your latest data")
    print_disclaimer(console)


def _confirm_schema(mapping: SchemaMapping, headers: list[str], examples: dict[str, str] | None = None) -> bool:
    """Display detected schema and ask user to confirm."""
    console.print()
    console.print("  Detected schema:")
    console.print("  " + "\u2500" * 40)

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Field", style="cyan")
    table.add_column("Column", style="white")
    table.add_column("Example", style="dim")

    ex = examples or {}

    table.add_row("date", f'"{mapping.date}"', ex.get("date", ""))
    table.add_row("ticker", f'"{mapping.ticker}"', ex.get("ticker", ""))
    buy_vals = ", ".join(mapping.buy_values)
    sell_vals = ", ".join(mapping.sell_values)
    table.add_row(
        "action",
        f'"{mapping.action}"',
        f"[buy: {buy_vals}]  [sell: {sell_vals}]",
    )
    table.add_row("quantity", f'"{mapping.quantity}"', ex.get("quantity", ""))
    if mapping.proceeds:
        table.add_row("proceeds", f'"{mapping.proceeds}"', ex.get("proceeds", ""))
    if mapping.cost_basis:
        table.add_row("cost_basis", f'"{mapping.cost_basis}"', ex.get("cost_basis", ""))
    if mapping.option_format:
        table.add_row("options", f'"{mapping.option_format}"', "")

    console.print(table)
    console.print("  " + "\u2500" * 40)

    import questionary

    return questionary.confirm("Does this look correct?", default=True).ask()
