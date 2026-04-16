# src/net_alpha/cli/wizard.py
from __future__ import annotations

import re
from pathlib import Path

import questionary
from rich.console import Console

from net_alpha.cli.output import print_disclaimer
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


def run_wizard(settings: Settings) -> None:
    """Interactive first-run wizard. Runs when `net-alpha` is called with no trades."""
    console.print()
    console.print("  [bold]Welcome to net-alpha[/bold] — cross-account wash sale detection.")
    console.print("  The only open-source tool that tracks wash sales across all your accounts.")
    console.print()

    # Check for API key
    if not settings.anthropic_api_key:
        console.print("  To detect CSV formats, net-alpha uses a one-time AI call per broker.")
        console.print("  You'll need an Anthropic API key (https://console.anthropic.com/keys).")
        console.print()
        api_key = questionary.text(
            "Enter your Anthropic API key:",
            validate=lambda x: len(x) > 10 or "Key must be at least 10 characters",
        ).ask()

        if api_key:
            _save_api_key(settings, api_key)
            settings.anthropic_api_key = api_key
            console.print("  [green]API key saved to ~/.net_alpha/config.toml[/green]")
        else:
            console.print("  [yellow]No API key provided. You can set ANTHROPIC_API_KEY later.[/yellow]")
            return

    # Import loop
    while True:
        console.print()
        broker = questionary.autocomplete(
            "Which broker is your next account?",
            choices=KNOWN_BROKERS,
            validate=lambda x: len(x) > 0 or "Broker name required",
        ).ask()

        if not broker:
            break

        csv_path_str = questionary.path(
            f"Path to {broker} CSV file:",
            validate=lambda x: Path(x).exists() or "File not found",
        ).ask()

        if not csv_path_str:
            break

        # Run import
        from net_alpha.cli.import_cmd import import_command

        try:
            import_command(broker=broker, file=Path(csv_path_str))
        except SystemExit:
            pass
        except Exception as e:
            console.print(f"  [red]Error:[/red] Import failed: {e}")
            continue

        another = questionary.confirm("Do you have another account to import?", default=False).ask()

        if not another:
            break

    # Run first check
    console.print()
    console.print("  Running your first wash sale check...")
    console.print()

    from net_alpha.cli.check import check_command

    try:
        check_command()
    except (SystemExit, Exception):
        pass

    console.print()
    console.print("  [green]\u2713 You're set up. Here's what to run next:[/green]")
    console.print()
    console.print("    [bold]net-alpha check[/bold]              Re-scan for wash sales anytime")
    console.print("    [bold]net-alpha simulate sell[/bold]      Check a trade before you make it")
    console.print("    [bold]net-alpha status[/bold]             See your full picture at a glance")
    console.print("    [bold]net-alpha report --csv[/bold]       Export for your tax preparer")
    print_disclaimer(console)


def _save_api_key(settings: Settings, api_key: str) -> None:
    """Write API key to config.toml."""
    config_path = settings.config_toml_path
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Read existing config or start fresh
    content = ""
    if config_path.exists():
        content = config_path.read_text()

    if "anthropic_api_key" in content:
        # Replace existing
        content = re.sub(
            r'anthropic_api_key\s*=\s*"[^"]*"',
            f'anthropic_api_key = "{api_key}"',
            content,
        )
    else:
        content += f'\nanthropic_api_key = "{api_key}"\n'

    config_path.write_text(content)
