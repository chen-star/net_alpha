# src/net_alpha/cli/default.py
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import typer
from sqlmodel import create_engine

from net_alpha.brokers.registry import detect_broker
from net_alpha.brokers.schwab import SchwabParser
from net_alpha.brokers.schwab_realized_gl import SchwabRealizedGLParser
from net_alpha.db.connection import init_db
from net_alpha.db.repository import Repository
from net_alpha.engine.detector import detect_in_window
from net_alpha.engine.etf_pairs import load_etf_pairs
from net_alpha.engine.merge import merge_violations
from net_alpha.engine.stitch import stitch_account
from net_alpha.ingest.csv_loader import compute_csv_sha256, load_csv
from net_alpha.ingest.dedup import filter_new
from net_alpha.models.domain import ImportRecord
from net_alpha.output import disclaimer, watch_list, ytd_impact
from net_alpha.splits.sync import _post_import_autosync_splits

ETF_PAIRS = load_etf_pairs(user_path=str(Path.home() / ".net_alpha" / "etf_pairs.yaml"))


def _engine():
    home = Path.home() / ".net_alpha"
    home.mkdir(parents=True, exist_ok=True)
    eng = create_engine(f"sqlite:///{home / 'net_alpha.db'}")
    init_db(eng)
    return eng


def run(csv_paths: list[str], account_label: str, detail: bool = False) -> int:
    repo = Repository(_engine())

    affected_dates: list = []
    account = None
    new_trade_total = 0
    dup_trade_total = 0
    new_gl_total = 0
    existing_symbols = {lot.ticker for lot in repo.all_lots() if lot.option_details is None}
    new_symbols: set[str] = set()

    for csv_path in csv_paths:
        headers, rows = load_csv(csv_path)
        parser = detect_broker(headers)
        if parser is None:
            typer.echo(
                f"Error: Could not detect broker from CSV headers in {csv_path}.\n"
                f"       Supported parsers: schwab (transactions), schwab_realized_gl\n"
                f"       To request support: open an issue with an anonymized sample.",
                err=True,
            )
            return 2

        # Schwab account label is shared across all files in this invocation.
        if account is None:
            account = repo.get_or_create_account("schwab", account_label)

        if isinstance(parser, SchwabParser):
            try:
                trades = parser.parse(rows, account_display=account.display())
            except ValueError as e:
                typer.echo(f"Error: {e}", err=True)
                return 3
            existing = repo.existing_natural_keys(account.id)
            new = filter_new(trades, existing)
            rec = ImportRecord(
                account_id=account.id,
                csv_filename=Path(csv_path).name,
                csv_sha256=compute_csv_sha256(csv_path),
                imported_at=datetime.now(),
                trade_count=len(new),
            )
            result = repo.add_import(account, rec, new)
            dup_count = len(trades) - len(new)
            new_trade_total += result.new_trades
            dup_trade_total += dup_count
            for t in new:
                affected_dates.append(t.date)
                if t.option_details is None:
                    new_symbols.add(t.ticker)
            typer.echo(
                f"Detected: {parser.name} — imported {result.new_trades} new trades, "
                f"skipped {dup_count} duplicates ({Path(csv_path).name})"
            )

        elif isinstance(parser, SchwabRealizedGLParser):
            try:
                lots = parser.parse(rows, account_display=account.display())
            except ValueError as e:
                typer.echo(f"Error: {e}", err=True)
                return 3
            rec = ImportRecord(
                account_id=account.id,
                csv_filename=Path(csv_path).name,
                csv_sha256=compute_csv_sha256(csv_path),
                imported_at=datetime.now(),
                trade_count=0,
            )
            result = repo.add_import(account, rec, [])
            inserted = repo.add_gl_lots(account, result.import_id, lots)
            new_gl_total += inserted
            for lot in lots:
                affected_dates.append(lot.closed_date)
            typer.echo(f"Detected: {parser.name} — imported {inserted} G/L lot rows ({Path(csv_path).name})")

        else:
            typer.echo(f"Error: Unhandled parser type {parser.name}", err=True)
            return 4

    # Stitch + recompute, scoped to the affected ±30-day window
    if account is not None:
        stitched = stitch_account(repo, account.id)
        if stitched.from_gl or stitched.from_fifo or stitched.unknown:
            typer.echo(
                f"Stitched: {stitched.from_gl} sells from G/L · "
                f"{stitched.from_fifo} via FIFO · {stitched.unknown} unknown"
            )
        for w in stitched.warnings:
            typer.echo(f"  ⚠ {w}", err=True)

        if affected_dates:
            win_start = min(affected_dates) - timedelta(days=30)
            win_end = max(affected_dates) + timedelta(days=30)
            window_trades = repo.trades_in_window(win_start, win_end)
            det = detect_in_window(window_trades, win_start, win_end, etf_pairs=ETF_PAIRS)
            all_gl = repo.get_gl_lots_for_account(account.id)
            merged = merge_violations(
                engine_violations=det.violations,
                gl_lots_by_account={account.id: all_gl},
            )
            repo.replace_violations_in_window(win_start, win_end, merged)
            repo.replace_lots_in_window(win_start, win_end, det.lots)

    _post_import_autosync_splits(repo, new_symbols=new_symbols, existing_symbols=existing_symbols)

    today = date.today()
    typer.echo("")
    typer.echo(watch_list.render(repo.all_lots(), repo.all_violations(), today=today))
    typer.echo("")
    typer.echo(ytd_impact.render(repo.violations_for_year(today.year), year=today.year))
    if detail:
        from net_alpha.output import detail as detail_mod

        typer.echo("")
        typer.echo(detail_mod.render(repo.all_violations()))
    typer.echo("")
    typer.echo(disclaimer.render())
    return 0
