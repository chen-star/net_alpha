from __future__ import annotations

from rich.console import Console

DISCLAIMER = "⚠ This is informational only. Consult a tax professional before filing."


def print_disclaimer(console: Console) -> None:
    """Print the mandatory disclaimer at the end of every command output."""
    console.print()
    console.print(f"  {DISCLAIMER}", style="dim")


def format_currency(amount: float) -> str:
    """Format a dollar amount with commas and 2 decimal places."""
    if amount < 0:
        return f"(${abs(amount):,.2f})"
    return f"${amount:,.2f}"


def confidence_style(confidence: str) -> str:
    """Return the Rich style string for a confidence label."""
    return {
        "Confirmed": "bold red",
        "Probable": "bold yellow",
        "Unclear": "bold blue",
    }.get(confidence, "")


def format_currency_colored(amount: float) -> str:
    """Return Rich markup string with green/red color based on sign."""
    formatted = format_currency(amount)
    if amount > 0:
        return f"[green]{formatted}[/green]"
    elif amount < 0:
        return f"[red]{formatted}[/red]"
    return formatted


def print_hint(console: Console, text: str) -> None:
    """Print a single contextual nudge line before the disclaimer."""
    console.print(f"\n  [dim]\u2192 {text}[/dim]")
