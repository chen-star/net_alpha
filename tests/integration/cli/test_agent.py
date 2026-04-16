from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session
from typer.testing import CliRunner

from net_alpha.cli.app import app
from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db


@pytest.fixture
def agent_setup(tmp_path, monkeypatch):
    """Provide (runner, engine, settings) with patched _bootstrap for agent tests."""
    db_path = tmp_path / "net_alpha.db"
    engine = get_engine(db_path)
    init_db(engine)

    settings = Settings(
        data_dir=tmp_path,
        anthropic_api_key="test-key",
        agent_model="claude-haiku-4-5",
    )

    def fake_bootstrap():
        return settings, Session(engine)

    monkeypatch.setattr("net_alpha.cli.app._bootstrap", fake_bootstrap)
    return CliRunner(), engine, settings


def _make_text_response(text: str) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    resp = MagicMock()
    resp.stop_reason = "end_turn"
    resp.content = [block]
    return resp


def test_agent_command_registered():
    """Verify 'agent' is a registered command in the Typer app."""
    from typer.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert "agent" in result.output


def test_agent_exits_with_no_api_key(tmp_path, monkeypatch):
    """Agent should print an error and exit if no API key is configured."""
    db_path = tmp_path / "net_alpha.db"
    engine = get_engine(db_path)
    init_db(engine)

    settings_no_key = Settings(data_dir=tmp_path)  # no API key set

    def fake_bootstrap_no_key():
        return settings_no_key, Session(engine)

    monkeypatch.setattr("net_alpha.cli.app._bootstrap", fake_bootstrap_no_key)

    runner = CliRunner()
    result = runner.invoke(app, ["agent"], input="exit\n")
    assert result.exit_code == 1
    assert "API key" in result.output


def test_agent_full_session_turn(agent_setup, monkeypatch):
    """Smoke test: agent runs a session, Claude responds with text, user exits."""
    runner, engine, settings = agent_setup

    # Patch anthropic.Anthropic to return a fake client
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _make_text_response(
        "You have no wash sale violations. \u26a0 This is informational only. Consult a tax professional before filing."
    )

    with patch("anthropic.Anthropic", return_value=fake_client):
        result = runner.invoke(
            app,
            ["agent"],
            input="Do I have any wash sales?\nexit\n",
        )

    assert result.exit_code == 0
    assert "You have no wash sale violations" in result.output
    assert "Goodbye" in result.output
