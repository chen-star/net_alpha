"""`net-alpha straddles` — list active §1092 offsetting groups + suspensions."""

from __future__ import annotations

import typer

from net_alpha.cli.default import _engine
from net_alpha.db.repository import Repository
from net_alpha.output import disclaimer
from net_alpha.output.straddles import render_straddles
from net_alpha.section_1092.detector import detect_offsetting_groups
from net_alpha.section_1092.holding_period import compute_suspensions
from net_alpha.section_1092.prices import cached_underlying_prices


def run(detail: bool = False) -> int:
    repo = Repository(_engine())
    trades = repo.all_trades()
    lots = repo.all_lots()
    prices = cached_underlying_prices(repo, (t.ticker for t in trades))

    groups = detect_offsetting_groups(trades=trades, lots=lots, underlying_prices=prices)
    suspensions = compute_suspensions(groups)

    typer.echo(render_straddles(groups=groups, suspensions=suspensions, detail=detail))
    typer.echo("")
    typer.echo(disclaimer.render())
    return 0
