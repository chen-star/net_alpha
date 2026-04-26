# tests/test_config.py
import tempfile
from pathlib import Path

import yaml

from net_alpha.config import Settings, load_pricing_config


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


def test_pricing_config_defaults_when_no_file(tmp_path):
    cfg = load_pricing_config(tmp_path / "config.yaml")
    assert cfg.enable_remote is True
    assert cfg.source == "yahoo"
    assert cfg.cache_ttl_seconds == 900


def test_pricing_config_reads_from_yaml(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.safe_dump({"prices": {"enable_remote": False, "cache_ttl_seconds": 60}}))
    cfg = load_pricing_config(config_file)
    assert cfg.enable_remote is False
    assert cfg.source == "yahoo"  # default preserved
    assert cfg.cache_ttl_seconds == 60


def test_settings_exposes_config_yaml_path():
    settings = Settings(data_dir=Path("/tmp/x"))
    assert settings.config_yaml_path == Path("/tmp/x/config.yaml")


def test_pricing_config_returns_defaults_on_type_validation_error(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("prices:\n  cache_ttl_seconds: not-a-number\n")
    cfg = load_pricing_config(config_file)
    assert cfg.cache_ttl_seconds == 900  # default preserved
