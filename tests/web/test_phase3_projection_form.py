"""Phase 3 inline projection form (§6.2 Pr1, Pr2)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_projection_tab_renders_inline_form_not_yaml_snippet(client: TestClient):
    resp = client.get("/tax?view=projection")
    html = resp.text
    # The inline form is present (Pr1).
    assert 'data-testid="projection-form"' in html
    # The YAML-snippet "save this to config.yaml" copy is gone.
    assert "save the snippet" not in html.lower()
    assert "save this to" not in html.lower()


def test_projection_form_post_persists_to_config_yaml(
    client: TestClient,
    settings,
):
    """POST /tax/projection-config writes the config.yaml in the app's data_dir.
    Asserts the file was written; doesn't depend on whether the app
    hot-reloads the config."""
    resp = client.post(
        "/tax/projection-config",
        data={
            "filing_status": "single",
            "state": "CA",
            "federal_marginal_rate": "0.32",
            "state_marginal_rate": "0.093",
            "ltcg_rate": "0.15",
            "qualified_div_rate": "0.15",
        },
    )
    # 200 with re-rendered fragment OR 303 redirect — accept either.
    assert resp.status_code in (200, 303)

    # File-level roundtrip: confirm the writer landed the data.
    import yaml

    cfg_path = settings.config_yaml_path
    assert cfg_path.exists(), f"config.yaml not written at {cfg_path}"
    data = yaml.safe_load(cfg_path.read_text())
    assert "tax" in data
    assert data["tax"]["filing_status"] == "single"
    assert data["tax"]["state"] == "CA"
    assert float(data["tax"]["federal_marginal_rate"]) == 0.32


def test_projection_form_writer_preserves_other_top_level_keys(tmp_path, monkeypatch):
    """The writer must not clobber unrelated top-level keys
    (e.g., etf_pairs, prices) in config.yaml."""
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg_dir = tmp_path / ".net_alpha"
    cfg_dir.mkdir(parents=True)
    cfg_path = cfg_dir / "config.yaml"

    # Pre-existing config with other keys
    import yaml

    cfg_path.write_text(
        yaml.safe_dump(
            {
                "etf_pairs": [{"a": "VOO", "b": "SPY"}],
                "prices": {"enable_remote": True},
            }
        )
    )

    from net_alpha.config import write_tax_config

    write_tax_config(
        {
            "filing_status": "single",
            "state": "TX",
            "federal_marginal_rate": 0.22,
            "state_marginal_rate": 0.0,
            "ltcg_rate": 0.15,
            "qualified_div_rate": 0.15,
        },
        path=cfg_path,
    )

    data = yaml.safe_load(cfg_path.read_text())
    assert "etf_pairs" in data, "etf_pairs key was clobbered"
    assert "prices" in data, "prices key was clobbered"
    assert data["tax"]["state"] == "TX"
