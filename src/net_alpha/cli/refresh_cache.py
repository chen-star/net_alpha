# src/net_alpha/cli/refresh_cache.py
"""Repair the historical_price_cache by purging negative-cached trading-day
entries and re-warming from the live provider.

This recovery path exists because earlier versions of `warm_historical_range`
stored ``None`` for every calendar day in a requested range when the
yfinance bulk response was partial. That permanently negative-cached real
trading days, which made `account_value_at` silently treat those holdings
as $0 — under-anchoring period starting values and inflating Total Return.

The current warmer no longer poisons trading days (only weekends are
authoritatively negative-cached). This command lets users repair existing
DBs created before that fix.
"""

from __future__ import annotations

from datetime import date, timedelta

import typer
from sqlalchemy import text

from net_alpha.cli.default import _engine
from net_alpha.config import Settings, load_pricing_config
from net_alpha.db.repository import Repository
from net_alpha.pricing.cache import PriceCache
from net_alpha.pricing.service import PricingService
from net_alpha.pricing.yahoo import YahooPriceProvider


def run(since: str | None, yes: bool) -> int:
    """Purge NULL historical cache rows (>= ``since`` if given) and re-warm.

    Returns a typer-style exit code.
    """
    since_date: date | None = None
    if since is not None:
        try:
            since_date = date.fromisoformat(since)
        except ValueError:
            typer.echo(f"Error: --since must be YYYY-MM-DD (got {since!r}).", err=True)
            return 2

    eng = _engine()
    cache = PriceCache(eng)
    repo = Repository(eng)

    # Show the user what's about to happen and require explicit confirmation.
    sql = "SELECT COUNT(*) FROM historical_price_cache WHERE close_price IS NULL"
    params: dict[str, str] = {}
    if since_date is not None:
        sql += " AND on_date >= :since"
        params["since"] = since_date.isoformat()
    with eng.connect() as conn:
        null_count = conn.execute(text(sql), params).scalar_one()
    if null_count == 0:
        typer.echo("No NULL historical cache rows to purge — nothing to do.")
        return 0

    scope = f"on_date >= {since_date.isoformat()}" if since_date else "all dates"
    typer.echo(f"Found {null_count} NULL historical cache rows ({scope}).")
    if not yes:
        confirm = typer.confirm("Purge these rows and re-warm from yfinance?")
        if not confirm:
            return 0

    deleted = cache.purge_historical_negatives(since=since_date)
    typer.echo(f"Purged {deleted} rows.")

    # Symbols to re-warm: every ticker we currently track holdings for. Using
    # lots-derived symbols (rather than every ticker that ever appeared in the
    # cache) keeps the warm scope tight to what affects starting-value math.
    symbols = sorted({lot.ticker for lot in repo.all_lots() if lot.option_details is None})
    if not symbols:
        typer.echo("No equity lots to re-warm — done.")
        return 0

    pcfg = load_pricing_config(Settings().config_yaml_path)
    if not pcfg.enable_remote:
        typer.echo("Remote prices are disabled (prices.enable_remote = false). Purge done; no re-warm performed.")
        return 0

    svc = PricingService(provider=YahooPriceProvider(), cache=cache, enabled=True)
    today = date.today()
    warm_start = since_date or _earliest_lot_date(repo) or today - timedelta(days=730)
    typer.echo(f"Re-warming {len(symbols)} symbols from {warm_start} to {today} ...")
    svc.warm_historical_range(symbols, warm_start, today)
    typer.echo("Done. Reopen the Total Return panel to verify the starting value.")
    return 0


def _earliest_lot_date(repo: Repository) -> date | None:
    earliest: date | None = None
    for lot in repo.all_lots():
        if earliest is None or lot.date < earliest:
            earliest = lot.date
    return earliest
