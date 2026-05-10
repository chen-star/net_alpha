"""`net-alpha straddles` — list active §1092 offsetting groups + suspensions."""

from __future__ import annotations

from decimal import Decimal

import typer

from net_alpha.cli.default import _engine
from net_alpha.db.repository import Repository
from net_alpha.output import disclaimer
from net_alpha.output.straddles import render_straddles
from net_alpha.section_1092.detector import detect_offsetting_groups
from net_alpha.section_1092.holding_period import compute_suspensions


def _underlying_prices(repo: Repository) -> dict[str, Decimal]:
    """Best-effort price lookup from the existing PriceCache. Missing tickers
    drop out — the detector handles missing-price entries gracefully."""
    out: dict[str, Decimal] = {}
    try:
        from net_alpha.pricing.cache import PriceCache  # late import; pricing is optional

        cache = PriceCache(repo.engine)
        for sym, quote in cache.snapshot().items():
            out[sym] = Decimal(str(quote.price))
    except Exception:  # noqa: BLE001 — cache is best-effort
        pass
    return out


def run(detail: bool = False) -> int:
    repo = Repository(_engine())
    trades = repo.all_trades()
    lots = repo.all_lots()
    prices = _underlying_prices(repo)

    groups = detect_offsetting_groups(trades=trades, lots=lots, underlying_prices=prices)
    suspensions = compute_suspensions(groups)

    typer.echo(render_straddles(groups=groups, suspensions=suspensions, detail=detail))
    typer.echo("")
    typer.echo(disclaimer.render())
    return 0
