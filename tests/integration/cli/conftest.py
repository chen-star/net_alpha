"""CLI-tier integration test fixtures."""

from __future__ import annotations

import pytest
from sqlmodel import Session
from typer.testing import CliRunner

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db


@pytest.fixture
def cli_setup(tmp_path, monkeypatch):
    """
    Provides (runner, engine, settings) for CLI integration tests.

    Patches net_alpha.cli.app._bootstrap to return Settings pointing at
    tmp_path and a fresh Session on each call. Tests that need to pre-seed
    data should open their own Session(engine), save, commit, close — then
    invoke the CLI (which gets a fresh session via the patched _bootstrap).
    """
    db_path = tmp_path / "net_alpha.db"
    engine = get_engine(db_path)
    init_db(engine)

    settings = Settings(data_dir=tmp_path)

    def fake_bootstrap():
        return settings, Session(engine)

    monkeypatch.setattr("net_alpha.cli.app._bootstrap", fake_bootstrap)

    runner = CliRunner()
    return runner, engine, settings
