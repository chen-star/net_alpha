from __future__ import annotations

import typer
from rich.console import Console
from sqlmodel import Session

from net_alpha.cli.import_cmd import import_command
from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.migrations import run_migrations

app = typer.Typer(
    name="net-alpha",
    help="Cross-account wash sale detection for equities, options, and ETFs.",
    no_args_is_help=False,
)
console = Console()

app.command(name="import")(import_command)


def _bootstrap() -> tuple[Settings, Session]:
    """Initialize settings, DB engine, run migrations, return (settings, session)."""
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    engine = get_engine(settings.db_path)
    init_db(engine)
    run_migrations(engine)
    return settings, Session(engine)


@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context):
    """Entry point — runs wizard if no command given and no trades exist."""
    if ctx.invoked_subcommand is not None:
        return

    settings, session = _bootstrap()
    from net_alpha.db.repository import TradeRepository

    repo = TradeRepository(session)
    trade_count = len(repo.list_all())
    session.close()

    if trade_count == 0:
        # First-run wizard
        from net_alpha.cli.wizard import run_wizard

        run_wizard(settings)
    else:
        # Show help if trades exist but no command given
        console.print(ctx.get_help())


def main():
    app()
