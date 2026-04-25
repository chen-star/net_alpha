# src/net_alpha/cli/default.py
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import typer
from sqlmodel import SQLModel, create_engine

from net_alpha.brokers.registry import detect_broker
from net_alpha.db.repository import Repository
from net_alpha.engine.detector import detect_in_window
from net_alpha.ingest.csv_loader import compute_csv_sha256, load_csv
from net_alpha.ingest.dedup import filter_new
from net_alpha.models.domain import ImportRecord
from net_alpha.output import disclaimer, watch_list, ytd_impact


def _engine():
    home = Path.home() / ".net_alpha"
    home.mkdir(parents=True, exist_ok=True)
    eng = create_engine(f"sqlite:///{home / 'net_alpha.db'}")
    SQLModel.metadata.create_all(eng)
    return eng


def run(csv_paths: list[str], account_label: str, detail: bool = False) -> int:
    repo = Repository(_engine())

    all_new_trades = []
    for csv_path in csv_paths:
        headers, rows = load_csv(csv_path)
        parser = detect_broker(headers)
        if parser is None:
            typer.echo(
                f"Error: Could not detect broker from CSV headers in {csv_path}.\n"
                f"       Supported brokers: schwab\n"
                f"       To request support: open an issue with an anonymized sample.",
                err=True,
            )
            return 2

        account = repo.get_or_create_account(parser.name, account_label)
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
            trade_count=0,
        )
        result = repo.add_import(account, rec, new)
        dup_count = len(trades) - len(new)
        typer.echo(
            f"Detected broker: {parser.name}\n"
            f"Imported {result.new_trades} new trades into account "
            f"'{account.display()}' ({dup_count} duplicates skipped)."
        )
        all_new_trades.extend(new)

    if all_new_trades:
        win_start = min(t.date for t in all_new_trades) - timedelta(days=30)
        win_end = max(t.date for t in all_new_trades) + timedelta(days=30)
        window_trades = repo.trades_in_window(win_start, win_end)
        new_violations = detect_in_window(window_trades, win_start, win_end, etf_pairs={}).violations
        repo.replace_violations_in_window(win_start, win_end, new_violations)

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
