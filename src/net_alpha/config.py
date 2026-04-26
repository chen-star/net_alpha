# src/net_alpha/config.py
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError

_DEFAULT_DATA_DIR = Path.home() / ".net_alpha"


class Settings(BaseModel):
    """Application settings for v2 (local-only, no LLM)."""

    model_config = {"extra": "ignore"}

    data_dir: Path = Field(default=_DEFAULT_DATA_DIR)
    db_name: str = "net_alpha.db"

    @property
    def db_path(self) -> Path:
        return self.data_dir / self.db_name

    @property
    def user_etf_pairs_path(self) -> Path:
        return self.data_dir / "etf_pairs.yaml"

    @property
    def config_toml_path(self) -> Path:
        return self.data_dir / "config.toml"

    @property
    def config_yaml_path(self) -> Path:
        return self.data_dir / "config.yaml"


class PricingConfig(BaseModel):
    model_config = {"extra": "ignore"}
    enable_remote: bool = True
    source: str = "yahoo"
    cache_ttl_seconds: int = 900


def load_pricing_config(path: Path) -> PricingConfig:
    """Load PricingConfig from a YAML file; returns defaults if missing/invalid."""
    if not path.exists():
        return PricingConfig()
    try:
        data = yaml.safe_load(path.read_text()) or {}
        return PricingConfig(**(data.get("prices") or {}))
    except (yaml.YAMLError, ValidationError):
        return PricingConfig()
