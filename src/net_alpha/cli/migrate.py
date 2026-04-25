# src/net_alpha/cli/migrate.py
from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

import typer
from sqlmodel import SQLModel, create_engine

from net_alpha.db.repository import Repository
from net_alpha.models.domain import ImportRecord, Trade


def run(yes: bool) -> int:
    home = Path.home() / ".net_alpha"
    v1 = home / "net_alpha.db"
    v2 = home / "net_alpha.db.v2"

    if not v1.exists():
        typer.echo(f"No v1 DB found at {v1}.", err=True)
        return 1
    if v2.exists():
        typer.echo(f"v2 DB already exists at {v2}. Refusing to overwrite.", err=True)
        return 1
    if not yes:
        if not typer.confirm(f"Migrate v1 DB at {v1} into a new v2 DB at {v2}?"):
            return 0

    con = sqlite3.connect(str(v1))
    rows = con.execute("SELECT account, date, ticker, action, quantity, proceeds, cost_basis FROM trades").fetchall()
    con.close()

    # Group trades by the v1 `account` field to support multi-account v1 DBs.
    # Each distinct account value becomes a separate v2 Account (broker=schwab).
    from collections import defaultdict

    by_account: dict[str, list[tuple]] = defaultdict(list)
    for row in rows:
        acct_label = row[0] or "default"
        by_account[acct_label].append(row)

    eng = create_engine(f"sqlite:///{v2}")
    SQLModel.metadata.create_all(eng)
    repo = Repository(eng)

    total_migrated = 0
    for acct_label, acct_rows in by_account.items():
        account = repo.get_or_create_account("schwab", acct_label)
        trades: list[Trade] = []
        for _acct, d, ticker, action, qty, proceeds, basis in acct_rows:
            trades.append(
                Trade(
                    account=account.display(),
                    date=date.fromisoformat(d),
                    ticker=ticker,
                    action=action,
                    quantity=qty,
                    proceeds=proceeds,
                    cost_basis=basis,
                )
            )
        record = ImportRecord(
            account_id=account.id,
            csv_filename="(migrated from v1)",
            csv_sha256="",
            imported_at=datetime.now(),
            trade_count=0,
        )
        result = repo.add_import(account, record, trades)
        total_migrated += result.new_trades

    typer.echo(
        f"Migrated {total_migrated} trades from {v1} into {v2}.\n"
        f"To use the new DB, move it into place:\n"
        f"  mv {v1} {v1}.v1.bak && mv {v2} {v1}"
    )
    return 0
