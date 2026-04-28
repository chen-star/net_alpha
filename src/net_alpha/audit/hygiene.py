"""Data hygiene: surface trade/lot/cash data quality issues for triage."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from net_alpha.db.repository import Repository

HygieneCategory = Literal["unpriced", "basis_unknown", "orphan_sell", "dup_key"]
HygieneSeverity = Literal["info", "warn", "error"]


class HygieneFixForm(BaseModel):
    """An inline HTMX form rendered on a hygiene row."""

    action: str                   # POST endpoint, e.g. /audit/set-basis
    fields: dict[str, str]        # field name -> field type ("date" | "number" | "text")
    hidden: dict[str, str]        # hidden form values, e.g. {"trade_id": "..."}


class HygieneIssue(BaseModel):
    category: HygieneCategory
    severity: HygieneSeverity
    summary: str
    detail: str
    fix_url: str | None = None
    fix_form: HygieneFixForm | None = None


def collect_issues(repo: Repository) -> list[HygieneIssue]:
    """Run all category checks against the current Repository state."""
    issues: list[HygieneIssue] = []
    issues.extend(_check_unpriced(repo))
    issues.extend(_check_basis_unknown(repo))
    issues.extend(_check_orphan_sells(repo))
    issues.extend(_check_dup_keys(repo))
    return issues


def _check_unpriced(repo: Repository) -> list[HygieneIssue]:
    """Open lots whose ticker has no current price quote."""
    return []


def _check_basis_unknown(repo: Repository) -> list[HygieneIssue]:
    """Buy trades flagged ``basis_unknown=True`` (transfer-in without basis)."""
    return []


def _check_orphan_sells(repo: Repository) -> list[HygieneIssue]:
    """Sell trades with no buy lot of the same ticker in the repository."""
    return []


def _check_dup_keys(repo: Repository) -> list[HygieneIssue]:
    """Same-day repeat clusters of ≥3 identical trades — possible re-import."""
    return []
