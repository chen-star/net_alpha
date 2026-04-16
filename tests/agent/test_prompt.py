from __future__ import annotations

from net_alpha.agent.prompt import build_state_snapshot, build_system_prompt
from net_alpha.cli.output import DISCLAIMER


def test_build_system_prompt_contains_disclaimer_rule():
    prompt = build_system_prompt("some snapshot")
    assert DISCLAIMER in prompt


def test_build_system_prompt_contains_snapshot():
    prompt = build_system_prompt("3 violations found")
    assert "3 violations found" in prompt


def test_build_system_prompt_contains_wash_sale_knowledge():
    prompt = build_system_prompt("")
    assert "wash sale" in prompt.lower()
    assert "30-day" in prompt


def test_build_system_prompt_contains_today_date():
    from datetime import date

    prompt = build_system_prompt("snapshot")
    assert date.today().isoformat() in prompt


def test_build_state_snapshot_includes_both_sections():
    snap = build_state_snapshot(status_output="status text", check_output="check text")
    assert "status text" in snap
    assert "check text" in snap


def test_build_state_snapshot_status_only():
    snap = build_state_snapshot(status_output="status text", check_output="")
    assert "status text" in snap
    assert "check text" not in snap


def test_build_state_snapshot_empty_returns_fallback():
    snap = build_state_snapshot(status_output="", check_output="")
    assert "No data" in snap
