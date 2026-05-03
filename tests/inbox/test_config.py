from pathlib import Path

import yaml

from net_alpha.inbox.config import InboxConfig, load_inbox_config


def test_defaults_when_file_missing(tmp_path: Path):
    cfg = load_inbox_config(tmp_path / "config.yaml")
    assert cfg == InboxConfig()
    assert cfg.wash_rebuy_visible_days == 14
    assert cfg.lt_lookahead_days == 60
    assert cfg.option_expiry_lookahead_days == 14
    assert cfg.assignment_risk_window_days == 7


def test_defaults_when_section_absent(tmp_path: Path):
    p = tmp_path / "config.yaml"
    p.write_text(yaml.safe_dump({"tax": {}}))
    cfg = load_inbox_config(p)
    assert cfg == InboxConfig()


def test_partial_override(tmp_path: Path):
    p = tmp_path / "config.yaml"
    p.write_text(yaml.safe_dump({"inbox": {"lt_lookahead_days": 90}}))
    cfg = load_inbox_config(p)
    assert cfg.lt_lookahead_days == 90
    assert cfg.wash_rebuy_visible_days == 14  # default preserved


def test_full_override(tmp_path: Path):
    p = tmp_path / "config.yaml"
    p.write_text(
        yaml.safe_dump(
            {
                "inbox": {
                    "wash_rebuy_visible_days": 7,
                    "lt_lookahead_days": 90,
                    "option_expiry_lookahead_days": 21,
                    "assignment_risk_window_days": 3,
                }
            }
        )
    )
    cfg = load_inbox_config(p)
    assert cfg.wash_rebuy_visible_days == 7
    assert cfg.lt_lookahead_days == 90
    assert cfg.option_expiry_lookahead_days == 21
    assert cfg.assignment_risk_window_days == 3
