# src/net_alpha/config.py
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Literal

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


class TaxConfig(BaseModel):
    """Optional tax configuration loaded from `~/.net_alpha/config.yaml` `tax:` section."""

    model_config = {"extra": "ignore"}

    filing_status: Literal["single", "mfj", "mfs", "hoh"] = "single"
    state: str = ""  # ISO state code; "" = federal-only
    federal_marginal_rate: Decimal = Decimal("0")
    state_marginal_rate: Decimal = Decimal("0")
    ltcg_rate: Decimal = Decimal("0.15")
    qualified_div_rate: Decimal = Decimal("0.15")
    reconciliation_tolerance: Decimal = Decimal("0.50")


def load_tax_config(path: Path) -> TaxConfig | None:
    """Load TaxConfig from a YAML file's ``tax:`` section. None if missing/invalid/absent."""
    if not path.exists():
        return None
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError:
        return None
    section = data.get("tax")
    if not section:
        return None
    try:
        return TaxConfig(**section)
    except ValidationError:
        return None


def write_tax_config(config: dict, path: Path | None = None) -> None:
    """Write or update the ``tax`` section of ``~/.net_alpha/config.yaml``.

    Preserves any other top-level keys (e.g., ``etf_pairs``, ``prices``)
    by reading the existing file (or starting from an empty dict) and
    merging only the ``tax`` key.

    Args:
        config: Dict of tax config fields (matching ``TaxConfig`` field names).
        path: Optional explicit path; defaults to ``~/.net_alpha/config.yaml``.
    """
    if path is None:
        path = Path.home() / ".net_alpha" / "config.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {}
    if path.exists():
        try:
            data = yaml.safe_load(path.read_text()) or {}
        except yaml.YAMLError:
            data = {}
    data["tax"] = config
    with path.open("w") as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
