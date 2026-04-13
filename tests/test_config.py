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
    assert settings.anthropic_model == "claude-haiku-4-5"
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
