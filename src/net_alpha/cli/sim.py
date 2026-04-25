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
    typer.echo("")
    typer.echo(disclaimer.render())
    return 0
