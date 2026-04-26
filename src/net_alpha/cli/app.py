# src/net_alpha/cli/app.py
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import typer
from typer.core import TyperGroup

from net_alpha.cli import default as default_cmd
from net_alpha.cli import imports as imports_cmd
from net_alpha.cli import migrate as migrate_cmd
from net_alpha.cli import sim as sim_cmd
from net_alpha.cli import ui as ui_cmd


class _FileFirstGroup(TyperGroup):
    """A Typer group that routes file-path arguments to the hidden 'run' sub-command.

    When the first non-option argument is not a known subcommand name, it must be
    a CSV file path. Prepend 'run' so the file-path argument reaches run_cmd.
    """

    def make_context(self, info_name, args, parent=None, **extra):
        if args:
            first_non_opt = next((a for a in args if not a.startswith("-")), None)
            if first_non_opt is not None and first_non_opt not in self.commands:
                args = ["run"] + list(args)
        return super().make_context(info_name, args, parent=parent, **extra)


app = typer.Typer(
    no_args_is_help=False,
    add_completion=False,
    cls=_FileFirstGroup,
)
imports_app = typer.Typer(no_args_is_help=False)
app.add_typer(imports_app, name="imports", help="List or remove past imports.")


# ---------------------------------------------------------------------------
# Hidden default command — handles `net-alpha <csv> [<csv>...] --account X`
# ---------------------------------------------------------------------------


@app.command(name="run", hidden=True, context_settings={"allow_interspersed_args": True})
def run_cmd(
    csv_paths: list[Path] = typer.Argument(..., help="One or more broker CSV files"),
    account: str | None = typer.Option(None, "--account", help="Required: account label"),
    detail: bool = typer.Option(False, "--detail", help="Show per-violation breakdown"),
):
    """Import one or more CSVs, run wash-sale detection, and render results."""
    if not account:
        typer.echo(
            "Error: --account is required for new imports.\n"
            "       Pass --account <label> to identify which account this CSV belongs to.\n"
            "       Example: net-alpha schwab.csv --account personal",
            err=True,
        )
        raise typer.Exit(2)
    raise typer.Exit(default_cmd.run([str(p) for p in csv_paths], account, detail=detail))


# ---------------------------------------------------------------------------
# sim command
# ---------------------------------------------------------------------------


@app.command(name="sim", help="Simulate a hypothetical sell.")
def sim(
    ticker: str,
    qty: float,
    price: float = typer.Option(..., "--price", help="Sell price per share"),
    account: str | None = typer.Option(None, "--account", help="Restrict to one account label"),
):
    raise typer.Exit(sim_cmd.run(ticker, Decimal(str(qty)), Decimal(str(price)), account))


@app.command(name="ui", help="Launch the local web UI in your browser.")
def ui(
    port: int | None = typer.Option(None, "--port", help="Override port (default: pick free in 8765-8775)."),
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't auto-open browser."),
    reload: bool = typer.Option(False, "--reload", help="Enable uvicorn auto-reload (dev)."),
):
    raise typer.Exit(ui_cmd.run(port=port, no_browser=no_browser, reload=reload))


# ---------------------------------------------------------------------------
# imports sub-app
# ---------------------------------------------------------------------------


@imports_app.callback(invoke_without_command=True)
def imports_default(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        raise typer.Exit(imports_cmd.list_cmd())


@imports_app.command(name="rm", help="Remove a past import by id.")
def imports_rm(
    import_id: int,
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    raise typer.Exit(imports_cmd.remove_cmd(import_id, yes))


# ---------------------------------------------------------------------------
# migrate-from-v1 command
# ---------------------------------------------------------------------------


@app.command(name="migrate-from-v1", help="One-shot migration of v1 DB into v2 schema.")
def migrate_from_v1(yes: bool = typer.Option(False, "--yes", "-y")):
    raise typer.Exit(migrate_cmd.run(yes))


# ---------------------------------------------------------------------------
# Root callback — shows help when no args given
# ---------------------------------------------------------------------------


@app.callback(invoke_without_command=True)
def root(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(0)


def main():
    app()
