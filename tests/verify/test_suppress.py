"""Phase 6 / Task 21: user-managed verify-finding suppression rules.

Source of truth: ``~/.net_alpha/config.yaml`` (or ``$NET_ALPHA_DIR/config.yaml``):

  verify:
    suppress:
      - rule_id: BasisRecon
        scope: BRK.B
        reason: '2023 spinoff handled differently by Schwab'
        until: 2027-01-01
"""

from __future__ import annotations

from datetime import date

from net_alpha.verify.suppress import (
    SuppressionRule,
    is_suppressed,
    load_suppressions,
)


def test_load_suppressions_returns_empty_when_no_config(tmp_path, monkeypatch):
    monkeypatch.setenv("NET_ALPHA_DIR", str(tmp_path))
    assert load_suppressions() == []


def test_load_suppressions_parses_yaml(tmp_path, monkeypatch):
    monkeypatch.setenv("NET_ALPHA_DIR", str(tmp_path))
    (tmp_path / "config.yaml").write_text(
        "verify:\n"
        "  suppress:\n"
        "    - rule_id: BasisRecon\n"
        "      scope: BRK.B\n"
        "      reason: 2023 spinoff\n"
        "      until: 2027-01-01\n"
    )
    rules = load_suppressions()
    assert len(rules) == 1
    assert rules[0].rule_id == "BasisRecon"
    assert rules[0].scope == "BRK.B"
    assert rules[0].until == date(2027, 1, 1)


def test_is_suppressed_matches_active_rule():
    rule = SuppressionRule(rule_id="BasisRecon", scope="BRK.B", reason="x", until=date(2027, 1, 1))
    assert (
        is_suppressed(
            rule_id="BasisRecon",
            scope="BRK.B/IRA",
            rules=[rule],
            today=date(2026, 5, 11),
        )
        is True
    )


def test_is_suppressed_ignores_expired_rule():
    rule = SuppressionRule(rule_id="BasisRecon", scope="BRK.B", reason="x", until=date(2025, 1, 1))
    assert (
        is_suppressed(
            rule_id="BasisRecon",
            scope="BRK.B/IRA",
            rules=[rule],
            today=date(2026, 5, 11),
        )
        is False
    )


def test_is_suppressed_requires_scope_match():
    rule = SuppressionRule(rule_id="BasisRecon", scope="BRK.B", reason="x", until=date(2027, 1, 1))
    assert (
        is_suppressed(
            rule_id="BasisRecon",
            scope="AAPL/Roth",
            rules=[rule],
            today=date(2026, 5, 11),
        )
        is False
    )


def test_load_suppressions_skips_malformed_entries(tmp_path, monkeypatch):
    """A missing required field on one entry must not nuke the entire list."""
    monkeypatch.setenv("NET_ALPHA_DIR", str(tmp_path))
    (tmp_path / "config.yaml").write_text(
        "verify:\n"
        "  suppress:\n"
        "    - rule_id: BasisRecon\n"
        "      # missing scope + until\n"
        "    - rule_id: QtyRecon\n"
        "      scope: AAPL\n"
        "      until: 2027-06-30\n"
    )
    rules = load_suppressions()
    assert len(rules) == 1
    assert rules[0].rule_id == "QtyRecon"
