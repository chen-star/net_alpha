# src/net_alpha/config.py
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

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
