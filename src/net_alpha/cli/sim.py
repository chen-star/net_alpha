# src/net_alpha/cli/sim.py
from __future__ import annotations

from decimal import Decimal

import typer

from net_alpha.cli.default import _engine
from net_alpha.db.repository import Repository
from net_alpha.engine.simulator import simulate_sell
from net_alpha.output import disclaimer, sim_result


def run(ticker: str, qty: Decimal, price: Decimal, account_label: str | None) -> int:
    repo = Repository(_engine())
    accounts = repo.list_accounts()
    if account_label:
        accounts = [a for a in accounts if a.label == account_label]
        if not accounts:
            typer.echo(f"Error: account with label '{account_label}' does not exist.", err=True)
            return 6

    options = simulate_sell(
        ticker=ticker,
        qty=qty,
        price=price,
        accounts=accounts,
        existing_lots=repo.all_lots(),
        recent_trades=repo.all_trades(),
    )
    if not options:
        typer.echo(f"Error: no holdings of {ticker}.", err=True)
        return 6

    typer.echo(sim_result.render(ticker, qty, price, options))

    # §1092 post-sell check: do the user's CURRENT holdings already form a
    # straddle? We don't simulate the post-sell state in v1 — we surface what
    # already exists so the user sees it on the same screen as the sim output.
    from net_alpha.section_1092.detector import detect_offsetting_groups

    groups = detect_offsetting_groups(trades=repo.all_trades(), lots=repo.all_lots())
    relevant = [g for g in groups if g.ticker == ticker]
    if relevant:
        typer.echo("")
        typer.echo("§1092 STRADDLE WARNING")
        typer.echo("-" * 60)
        for g in relevant:
            typer.echo(f"  • {g.kind} on {g.ticker} ({g.account}) — {g.rule_citation}")
        typer.echo("  Run `net-alpha straddles --detail` for the full breakdown.")

    typer.echo("")
    typer.echo(disclaimer.render())
    return 0
