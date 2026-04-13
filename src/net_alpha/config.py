# src/net_alpha/config.py
from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings

_DEFAULT_DATA_DIR = Path.home() / ".net_alpha"


class Settings(BaseSettings):
    """Application settings, loaded from env vars and ~/.net_alpha/config.toml."""

    model_config = {"env_file": None, "toml_file": None, "extra": "ignore"}

    data_dir: Path = Field(default=_DEFAULT_DATA_DIR)
    db_name: str = "net_alpha.db"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-haiku-4-5"
    llm_max_retries: int = 3

    @property
    def db_path(self) -> Path:
        return self.data_dir / self.db_name

    @property
    def user_etf_pairs_path(self) -> Path:
        return self.data_dir / "etf_pairs.yaml"

    @property
    def config_toml_path(self) -> Path:
        return self.data_dir / "config.toml"
