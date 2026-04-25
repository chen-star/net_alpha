from __future__ import annotations

import typer
from sqlmodel import Session

from net_alpha.cli.import_cmd import import_command
from net_alpha.cli.simulate import simulate_app
from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.migrations import migrate

app = typer.Typer(
    name="net-alpha",
    help="Cross-account wash sale detection for equities, options, and ETFs.",
    no_args_is_help=False,
)

app.command(name="import")(import_command)
app.add_typer(simulate_app, name="simulate")


def _bootstrap() -> tuple[Settings, Session]:
    """Initialize settings, DB engine, run migrations, return (settings, session)."""
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    engine = get_engine(settings.db_path)
    init_db(engine)
    with Session(engine) as mig_session:
        migrate(mig_session)
    return settings, Session(engine)


@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context):
    """Entry point — runs if no command given."""
    if ctx.invoked_subcommand is not None:
        return


def main():
    app()
