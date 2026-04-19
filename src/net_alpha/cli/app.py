from __future__ import annotations

import typer
from rich.console import Console
from sqlmodel import Session

from net_alpha.cli.agent import agent_command
from net_alpha.cli.check import check_command
from net_alpha.cli.import_cmd import import_command
from net_alpha.cli.rebuys import rebuys_command
from net_alpha.cli.report import report_command
from net_alpha.cli.simulate import simulate_app
from net_alpha.cli.status import status_command
from net_alpha.cli.tax_position import tax_position_command
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
app.command(name="check")(check_command)
app.add_typer(simulate_app, name="simulate")
app.command(name="rebuys")(rebuys_command)
app.command(name="report")(report_command)
app.command(name="tax-position")(tax_position_command)
app.command(name="status")(status_command)
app.command(name="agent")(agent_command)


@app.command(name="tui")
def tui_command():
    """Launch the interactive dashboard and simulator."""
    from net_alpha.cli.app import _bootstrap
    from net_alpha.db.repository import TradeRepository
    from net_alpha.tui.app import NetAlphaTUI

    settings, session = _bootstrap()
    try:
        repo = TradeRepository(session)
        trades = repo.list_all()
        tui_app = NetAlphaTUI(trades=trades, etf_pairs=settings.etf_pairs)
        tui_app.run()
    finally:
        session.close()


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
    """Entry point \u2014 runs wizard if no command given."""
    if ctx.invoked_subcommand is not None:
        return

    settings, session = _bootstrap()
    session.close()

    from net_alpha.cli.wizard import run_wizard

    run_wizard(settings)


@app.command(name="wizard")
def wizard_command():
    """Interactive wizard mode."""
    settings, session = _bootstrap()
    session.close()

    from net_alpha.cli.wizard import run_wizard

    run_wizard(settings)


def main():
    app()
