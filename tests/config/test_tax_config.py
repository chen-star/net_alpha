from decimal import Decimal
from pathlib import Path

from net_alpha.config import load_tax_config


def test_load_tax_config_returns_none_when_missing(tmp_path: Path) -> None:
    assert load_tax_config(tmp_path / "config.yaml") is None


def test_load_tax_config_returns_none_when_section_absent(tmp_path: Path) -> None:
    p = tmp_path / "config.yaml"
    p.write_text("prices:\n  enable_remote: true\n")
    assert load_tax_config(p) is None


def test_load_tax_config_parses_full_section(tmp_path: Path) -> None:
    p = tmp_path / "config.yaml"
    p.write_text(
        "tax:\n"
        "  filing_status: single\n"
        "  state: CA\n"
        "  federal_marginal_rate: 0.32\n"
        "  state_marginal_rate: 0.093\n"
        "  ltcg_rate: 0.15\n"
        "  qualified_div_rate: 0.15\n"
        "  reconciliation_tolerance: 0.50\n"
    )
    cfg = load_tax_config(p)
    assert cfg is not None
    assert cfg.filing_status == "single"
    assert cfg.state == "CA"
    assert cfg.federal_marginal_rate == Decimal("0.32")
    assert cfg.reconciliation_tolerance == Decimal("0.50")


def test_load_tax_config_defaults(tmp_path: Path) -> None:
    p = tmp_path / "config.yaml"
    p.write_text("tax:\n  filing_status: single\n  federal_marginal_rate: 0.22\n")
    cfg = load_tax_config(p)
    assert cfg is not None
    assert cfg.state == ""
    assert cfg.state_marginal_rate == Decimal("0")
    assert cfg.ltcg_rate == Decimal("0.15")
    assert cfg.qualified_div_rate == Decimal("0.15")
    assert cfg.reconciliation_tolerance == Decimal("0.50")


def test_load_tax_config_invalid_yaml_returns_none(tmp_path: Path) -> None:
    p = tmp_path / "config.yaml"
    p.write_text("tax: {{not yaml")
    assert load_tax_config(p) is None
