# src/net_alpha/cli/imports.py
from __future__ import annotations

from pathlib import Path

import typer

from net_alpha.cli.default import _engine
from net_alpha.db.repository import Repository
from net_alpha.engine.etf_pairs import load_etf_pairs
from net_alpha.engine.recompute import recompute_all_violations
from net_alpha.output.imports_table import render as render_table

ETF_PAIRS = load_etf_pairs(user_path=str(Path.home() / ".net_alpha" / "etf_pairs.yaml"))


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
        recompute_all_violations(repo, ETF_PAIRS)
        typer.echo("Recomputed wash sales over affected window.")
    return 0
