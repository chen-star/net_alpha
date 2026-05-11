"""Suppression list — user-acknowledged known issues that mute findings.

Format in ``~/.net_alpha/config.yaml`` (or ``$NET_ALPHA_DIR/config.yaml``):

    verify:
      suppress:
        - rule_id: BasisRecon
          scope: BRK.B
          reason: '2023 spinoff handled differently by Schwab'
          until: 2027-01-01

A rule mutes a finding when:
  * ``rule_id`` matches exactly, AND
  * the finding's ``scope`` starts with the rule's ``scope`` (so ``BRK.B``
    mutes ``BRK.B/IRA`` and ``BRK.B/Taxable``), AND
  * ``today <= until`` (rules auto-expire so a once-acknowledged issue can't
    silently hide a recurrence years later).

Malformed entries are ignored, not fatal — config-typo-during-edit should
never crash the verify job.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml


@dataclass(frozen=True)
class SuppressionRule:
    rule_id: str
    scope: str
    reason: str
    until: date


def _config_path() -> Path:
    """Mirror the path resolution used by ``verify.tolerances`` so a single
    ``$NET_ALPHA_DIR`` override drives both subsystems consistently."""
    base = os.environ.get("NET_ALPHA_DIR") or str(Path.home() / ".net_alpha")
    return Path(base) / "config.yaml"


def load_suppressions() -> list[SuppressionRule]:
    """Return the active suppression rules. Always returns a list (never None).

    Returns ``[]`` if the config file is missing, unreadable, or the ``verify:
    suppress:`` section is absent. Individual malformed entries inside an
    otherwise-valid list are skipped — the rest of the list still applies.
    """
    path = _config_path()
    if not path.exists():
        return []
    try:
        raw = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError:
        return []
    items = (raw.get("verify") or {}).get("suppress") or []
    out: list[SuppressionRule] = []
    for item in items:
        try:
            until = item["until"]
            until_d = until if isinstance(until, date) else date.fromisoformat(str(until))
            out.append(
                SuppressionRule(
                    rule_id=str(item["rule_id"]),
                    scope=str(item["scope"]),
                    reason=str(item.get("reason", "")),
                    until=until_d,
                )
            )
        except (KeyError, ValueError, TypeError):
            continue  # malformed entries are ignored, not fatal
    return out


def is_suppressed(
    *,
    rule_id: str,
    scope: str,
    rules: list[SuppressionRule],
    today: date,
) -> bool:
    """Return True iff ``(rule_id, scope)`` matches any active rule.

    A rule matches when ``rule_id`` is exact and ``scope`` *starts with*
    ``rule.scope`` — so a rule on ``"BRK.B"`` suppresses both ``"BRK.B/IRA"``
    and ``"BRK.B/Taxable"``. ``today > rule.until`` disqualifies an expired
    rule.
    """
    for r in rules:
        if r.rule_id != rule_id:
            continue
        if not scope.startswith(r.scope):
            continue
        if today > r.until:
            continue
        return True
    return False
