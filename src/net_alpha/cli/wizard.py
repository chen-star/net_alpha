# src/net_alpha/cli/wizard.py
from __future__ import annotations

import re
from pathlib import Path

import questionary
from rich.console import Console
from rich.panel import Panel

from net_alpha.config import Settings

console = Console()

KNOWN_BROKERS = [
    "schwab",
    "robinhood",
    "fidelity",
    "etrade",
    "td_ameritrade",
    "interactive_brokers",
    "webull",
    "tastytrade",
]


def print_teaching_tip(command_str: str) -> None:
    console.print()
    console.print(f"  [cyan]Tip: Next time, run:[/cyan] [bold]{command_str}[/bold]")
    console.print()


def run_wizard(settings: Settings) -> None:
    """Main interactive wizard mode."""
    console.print()
    console.print("  [bold]net-alpha Interactive Wizard[/bold]")
    console.print()

    while True:
        action = questionary.select(
            "What would you like to do?",
            choices=[
                questionary.Choice("Import new trade data (CSV)", "import"),
                questionary.Choice("Check for wash sales", "check"),
                questionary.Choice("Simulate a trade", "simulate"),
                questionary.Choice("Generate tax report", "report"),
                questionary.Choice("Ask the AI Assistant", "agent"),
                questionary.Choice("Exit", "exit"),
            ],
        ).ask()

        if action == "import":
            _wizard_import(settings)
        elif action == "check":
            _wizard_check()
        elif action == "simulate":
            _wizard_simulate()
        elif action == "report":
            _wizard_report()
        elif action == "agent":
            _wizard_agent()
        elif action in ("exit", None):
            console.print("  Goodbye!")
            break


def _ensure_api_key(settings: Settings) -> None:
    if not settings.anthropic_api_key:
        console.print("  You'll need an Anthropic API key to detect CSV formats or use the AI Assistant.")
        api_key = questionary.text(
            "Enter your Anthropic API key (or press enter to skip):",
        ).ask()
        if api_key:
            _save_api_key(settings, api_key)
            settings.anthropic_api_key = api_key
            console.print("  [green]API key saved to ~/.net_alpha/config.toml[/green]")
            console.print()


def _save_api_key(settings: Settings, api_key: str) -> None:
    config_path = settings.config_toml_path
    config_path.parent.mkdir(parents=True, exist_ok=True)
    content = ""
    if config_path.exists():
        content = config_path.read_text()
    if "anthropic_api_key" in content:
        content = re.sub(r'anthropic_api_key\s*=\s*"[^"]*"', f'anthropic_api_key = "{api_key}"', content)
    else:
        content += f'\nanthropic_api_key = "{api_key}"\n'
    config_path.write_text(content)


def _wizard_import(settings: Settings):
    broker = questionary.autocomplete(
        "Which broker?",
        choices=KNOWN_BROKERS,
    ).ask()
    if not broker:
        return

    csv_path_str = questionary.path(
        f"Path to {broker} CSV file:",
        validate=lambda x: Path(x).exists() or "File not found",
    ).ask()
    if not csv_path_str:
        return

    import typer

    from net_alpha.cli.import_cmd import import_command

    try:
        import_command(broker=broker, file=Path(csv_path_str))
    except (typer.Exit, SystemExit):
        pass
    except Exception as e:
        console.print(f"  [red]Error:[/red] {e}")

    print_teaching_tip(f"net-alpha import {broker} {csv_path_str}")

    # Prompt for next actions
    next_action = questionary.confirm("Do you want to check portfolio for wash sales now?", default=True).ask()
    if next_action:
        _wizard_check()


def _wizard_check():
    from net_alpha.cli.app import _bootstrap
    from net_alpha.cli.check import check_command
    from net_alpha.db.repository import TradeRepository
    from net_alpha.engine.detector import WashSaleDetector

    settings, session = _bootstrap()
    try:
        repo = TradeRepository(session)
        detector = WashSaleDetector(repo.list_all())
        results = detector.detect()

        confirmed = sum(1 for w in results.wash_sales if w.probability == 1.0)
        probable = sum(1 for w in results.wash_sales if w.probability < 1.0)
        disallowed = sum(w.disallowed_loss for w in results.wash_sales)

        summary_text = (
            f"[cyan]Total Wash Sales:[/cyan] {len(results.wash_sales)} ({confirmed} Confirmed, {probable} Probable)\n"
            f"[red]Total Disallowed Losses:[/red] ${disallowed:,.2f}"
        )
        panel = Panel(summary_text, title="[bold]Wash Sale Executive Summary[/bold]", expand=False)
        console.print()
        console.print(panel)
        console.print()

    except Exception as e:
        console.print(f"  [red]Error calculating summary:[/red] {e}")
    finally:
        session.close()

    action = questionary.select(
        "Drill-down options:",
        choices=["View detailed list", "Filter by Ticker", "Filter by Account", "Return to Menu"],
    ).ask()

    import typer

    cmd = "net-alpha check"

    try:
        if action == "View detailed list":
            check_command()
        elif action == "Filter by Ticker":
            ticker = questionary.text("Enter Ticker:").ask()
            if ticker:
                cmd = f"net-alpha check --ticker {ticker}"
                check_command(ticker=ticker)
        elif action == "Filter by Account":
            account = questionary.text("Enter Account/Broker:").ask()
            if account:
                cmd = f"net-alpha check --account {account}"
                check_command(account=account)
    except (typer.Exit, SystemExit, Exception):
        pass

    print_teaching_tip(cmd)


def _wizard_simulate():
    action = questionary.select("Action:", choices=["buy", "sell"]).ask()
    if not action:
        return
    ticker = questionary.text("Ticker symbol:").ask()
    if not ticker:
        return
    qty_str = questionary.text("Quantity:").ask()
    if not qty_str:
        return
    price_str = questionary.text("Estimated Price:").ask()
    if not price_str:
        return

    try:
        qty = float(qty_str)
        price = float(price_str)
    except Exception:
        console.print("Invalid numeric amounts.")
        return

    import typer

    from net_alpha.cli.simulate import buy_command, sell_command

    console.print()
    try:
        if action == "sell":
            sell_command(ticker, qty, price=price)
        else:
            buy_command(ticker, qty, price=price)
    except (typer.Exit, SystemExit, Exception):
        pass

    print_teaching_tip(f"net-alpha simulate {action} {ticker} {qty} --price {price}")


def _wizard_report():
    import typer

    from net_alpha.cli.report import report_command

    console.print()
    try:
        report_command()
    except (typer.Exit, SystemExit, Exception):
        pass
    print_teaching_tip("net-alpha report")


def _wizard_agent():
    import typer

    from net_alpha.cli.agent import agent_command

    console.print()
    try:
        agent_command()
    except (typer.Exit, SystemExit, Exception):
        pass
    print_teaching_tip("net-alpha agent")
