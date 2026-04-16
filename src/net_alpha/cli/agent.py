from __future__ import annotations

import subprocess

import typer
from rich.console import Console
from rich.panel import Panel

from net_alpha.cli.output import DISCLAIMER

console = Console()

_HELP_TEXT = """[bold]net-alpha agent[/bold] — natural language interface

Ask anything about your trades, wash sales, or tax position. Examples:

  "Do I have any wash sale violations this year?"
  "Should I sell my AAPL position?"
  "What's my YTD tax situation?"
  "Which positions can I safely rebuy?"
  "Check for wash sales on my TSLA trades"

Type [bold]exit[/bold] to quit. Prefix with [bold]![/bold] to run a raw CLI command."""

_EXIT_SENTINEL = "__exit__"


def _route_local(user_input: str) -> str | None:
    """
    Handle trivial inputs locally without an API call.

    Returns:
        "__exit__" if the user wants to quit
        A help string if user typed "help"
        None if the input should go to the ReAct loop
    """
    stripped = user_input.strip()
    if not stripped:
        return None
    if stripped.lower() in {"exit", "quit", "q"}:
        return _EXIT_SENTINEL
    if stripped.lower() == "help":
        return _HELP_TEXT
    return None


def agent_command() -> None:
    """Start an interactive AI assistant session for tax and wash sale questions."""
    from net_alpha.cli.app import _bootstrap

    settings, session = _bootstrap()
    session.close()  # Agent tools manage their own sessions via _bootstrap

    api_key = settings.resolved_agent_api_key
    if not api_key:
        console.print(
            "\n  [red]Error:[/red] No API key configured.\n"
            "  Set [bold]ANTHROPIC_API_KEY[/bold] or add "
            "[bold]anthropic_api_key[/bold] to [bold]~/.net_alpha/config.toml[/bold]"
        )
        raise typer.Exit(1)

    import anthropic

    from net_alpha.agent.prompt import build_state_snapshot, build_system_prompt
    from net_alpha.agent.react import run_react_turn
    from net_alpha.agent.tools import TOOL_SCHEMAS, execute_tool, run_check, run_status

    client = anthropic.Anthropic(api_key=api_key)
    model = settings.agent_model

    # Session-start scan
    console.print()
    with console.status("Scanning your portfolio\u2026", spinner="dots"):
        status_out = run_status()
        check_out = run_check(quiet=True)
        snapshot = build_state_snapshot(status_out, check_out)

    system_prompt = build_system_prompt(snapshot)

    console.print(Panel(snapshot, title="[bold]Portfolio Snapshot[/bold]", border_style="dim"))
    console.print()
    console.print(
        "  [bold]Agent ready.[/bold] Ask anything about your trades or tax position.\n"
        "  (Type [dim]help[/dim] for examples, [dim]exit[/dim] to quit)\n"
    )

    messages: list[dict] = []

    while True:
        try:
            user_input = console.input("  [bold green]You:[/bold green] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n  Goodbye.")
            break

        if not user_input:
            continue

        # Handle ! passthrough before other routing
        if user_input.startswith("!"):
            raw_cmd = user_input[1:].strip()
            console.print()
            subprocess.run(raw_cmd, shell=True)
            console.print()
            continue

        # Local fast-path
        local_response = _route_local(user_input)
        if local_response == _EXIT_SENTINEL:
            console.print("  Goodbye.")
            break
        if local_response is not None:
            console.print(f"\n{local_response}\n")
            continue

        # ReAct turn
        messages.append({"role": "user", "content": user_input})
        try:
            with console.status("Thinking\u2026", spinner="dots"):
                response = run_react_turn(
                    client, model, system_prompt, messages, TOOL_SCHEMAS, execute_tool
                )
        except Exception as e:
            console.print(f"\n  [red]API error:[/red] {e}\n  Try again or type [bold]exit[/bold].\n")
            messages.pop()  # Remove failed user message from history
            continue

        messages.append({"role": "assistant", "content": response})
        console.print(f"\n  [bold blue]Agent:[/bold blue] {response}\n")
