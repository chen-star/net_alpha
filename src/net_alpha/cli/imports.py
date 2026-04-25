# src/net_alpha/cli/imports.py
from __future__ import annotations

import typer

from net_alpha.cli.default import _engine
from net_alpha.db.repository import Repository
from net_alpha.engine.detector import detect_in_window
from net_alpha.output.imports_table import render as render_table


def list_cmd() -> int:
    repo = Repository(_engine())
    typer.echo(render_table(repo.list_imports()))
    return 0


def remove_cmd(import_id: int, yes: bool) -> int:
    repo = Repository(_engine())
    if repo.get_import(import_id) is None:
        typer.echo(f"Error: no import with id {import_id}. Run `net-alpha imports` to list.", err=True)
        return 5
    if not yes:
        confirm = typer.confirm(f"Remove import #{import_id}?")
        if not confirm:
            return 0
    result = repo.remove_import(import_id)
    typer.echo(f"Removed import #{import_id} ({result.removed_trade_count} trades).")

    if result.recompute_window is not None:
        win_start, win_end = result.recompute_window
        window_trades = repo.trades_in_window(win_start, win_end)
        new_violations = detect_in_window(window_trades, win_start, win_end, etf_pairs={}).violations
        repo.replace_violations_in_window(win_start, win_end, new_violations)
        typer.echo("Recomputed wash sales over affected window.")
    return 0
