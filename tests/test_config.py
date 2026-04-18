# tests/test_config.py
import tempfile
from pathlib import Path

from net_alpha.config import Settings


def test_default_settings():
    settings = Settings(
        _env_file=None,
        data_dir=Path(tempfile.mkdtemp()),
    )
    assert settings.db_name == "net_alpha.db"
    assert settings.anthropic_model == "claude-3-5-haiku-latest"
    assert settings.llm_max_retries == 3


def test_db_path():
    data_dir = Path(tempfile.mkdtemp())
    settings = Settings(_env_file=None, data_dir=data_dir)
    assert settings.db_path == data_dir / "net_alpha.db"


def test_etf_pairs_path():
    data_dir = Path(tempfile.mkdtemp())
    settings = Settings(_env_file=None, data_dir=data_dir)
    assert settings.user_etf_pairs_path == data_dir / "etf_pairs.yaml"


def test_anthropic_api_key_from_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
    settings = Settings(
        _env_file=None,
        data_dir=Path(tempfile.mkdtemp()),
    )
    assert settings.anthropic_api_key == "sk-test-123"


def test_agent_model_default():
    settings = Settings(_env_file=None, data_dir=Path(tempfile.mkdtemp()))
    assert settings.agent_model == "claude-3-5-haiku-latest"


def test_agent_api_key_defaults_to_none():
    settings = Settings(_env_file=None, data_dir=Path(tempfile.mkdtemp()))
    assert settings.agent_api_key is None


def test_resolved_agent_api_key_uses_agent_key_first():
    settings = Settings(
        _env_file=None,
        data_dir=Path(tempfile.mkdtemp()),
        agent_api_key="agent-key",
        anthropic_api_key="shared-key",
    )
    assert settings.resolved_agent_api_key == "agent-key"


def test_resolved_agent_api_key_falls_back_to_anthropic_key():
    settings = Settings(
        _env_file=None,
        data_dir=Path(tempfile.mkdtemp()),
        anthropic_api_key="shared-key",
    )
    assert settings.resolved_agent_api_key == "shared-key"


def test_resolved_agent_api_key_returns_none_when_neither_set():
    settings = Settings(_env_file=None, data_dir=Path(tempfile.mkdtemp()))
    assert settings.resolved_agent_api_key is None
