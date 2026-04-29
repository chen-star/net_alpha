"""/tax?view=performance route renders the after-tax performance panel."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import yaml
from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from net_alpha.config import Settings, TaxConfig
from net_alpha.db.connection import get_engine
from net_alpha.web.app import create_app


def _write_tax_config_to(settings: Settings, cfg: TaxConfig) -> None:
    """Write TaxConfig into the settings data_dir config.yaml before app startup."""
    path: Path = settings.config_yaml_path
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {}
    if path.exists():
        try:
            data = yaml.safe_load(path.read_text()) or {}
        except yaml.YAMLError:
            data = {}
    data["tax"] = {
        "filing_status": cfg.filing_status,
        "state": cfg.state,
        "federal_marginal_rate": float(cfg.federal_marginal_rate),
        "state_marginal_rate": float(cfg.state_marginal_rate),
        "ltcg_rate": float(cfg.ltcg_rate),
        "qualified_div_rate": float(cfg.qualified_div_rate),
    }
    with path.open("w") as f:
        yaml.safe_dump(data, f)


def test_performance_tab_renders_with_config(tmp_path):
    """When tax config is available, /tax?view=performance returns the panel."""
    settings = Settings(data_dir=tmp_path)
    _write_tax_config_to(
        settings,
        TaxConfig(
            filing_status="single",
            state="",
            federal_marginal_rate=Decimal("0.37"),
            state_marginal_rate=Decimal("0"),
            ltcg_rate=Decimal("0.20"),
            qualified_div_rate=Decimal("0.20"),
        ),
    )

    engine = get_engine(settings.db_path)
    SQLModel.metadata.create_all(engine)
    app = create_app(settings)
    client = TestClient(app, raise_server_exceptions=False)

    r = client.get("/tax?view=performance")
    assert r.status_code == 200
    assert "pre-tax" in r.text.lower()
    assert "after-tax" in r.text.lower()


def test_performance_tab_renders_setup_prompt_when_no_config(tmp_path):
    """When tax config is missing, render the existing missing-config CTA."""
    settings = Settings(data_dir=tmp_path)  # no config.yaml written

    engine = get_engine(settings.db_path)
    SQLModel.metadata.create_all(engine)
    app = create_app(settings)
    client = TestClient(app, raise_server_exceptions=False)

    r = client.get("/tax?view=performance", follow_redirects=False)
    assert r.status_code in {200, 303, 307}
    if r.status_code == 200:
        # The page renders some tax-related content (setup prompt or config form)
        assert "tax" in r.text.lower()
