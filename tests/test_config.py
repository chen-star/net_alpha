# tests/test_config.py
import tempfile
from pathlib import Path

from net_alpha.config import Settings


def test_default_settings():
    settings = Settings(data_dir=Path(tempfile.mkdtemp()))
    assert settings.db_name == "net_alpha.db"


def test_db_path():
    data_dir = Path(tempfile.mkdtemp())
    settings = Settings(data_dir=data_dir)
    assert settings.db_path == data_dir / "net_alpha.db"


def test_etf_pairs_path():
    data_dir = Path(tempfile.mkdtemp())
    settings = Settings(data_dir=data_dir)
    assert settings.user_etf_pairs_path == data_dir / "etf_pairs.yaml"


def test_config_toml_path():
    data_dir = Path(tempfile.mkdtemp())
    settings = Settings(data_dir=data_dir)
    assert settings.config_toml_path == data_dir / "config.toml"
