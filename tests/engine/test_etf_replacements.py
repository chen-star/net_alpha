from pathlib import Path

import pytest

from net_alpha.engine.etf_pairs import (
    ReplacementsConflictWarning,
    load_etf_pairs,
    load_etf_replacements,
)


def test_load_etf_replacements_bundled() -> None:
    repls = load_etf_replacements()
    assert "SPY" in repls
    assert "VTI" in repls["SPY"]


def test_user_replacements_extend_bundled(tmp_path: Path) -> None:
    user = tmp_path / "etf_replacements.yaml"
    user.write_text("SPY:\n  - SCHX\n")
    repls = load_etf_replacements(user_path=user)
    assert "VTI" in repls["SPY"]
    assert "SCHX" in repls["SPY"]


def test_replacements_consistency_filters_conflicts(tmp_path: Path) -> None:
    """A replacement must NEVER appear in the source's substantially-identical pairs."""
    user = tmp_path / "etf_replacements.yaml"
    # SPY's pairs include VOO/IVV/SPLG. If user adds VOO as a replacement, that's a conflict.
    user.write_text("SPY:\n  - VOO\n")
    pairs = load_etf_pairs()
    with pytest.warns(ReplacementsConflictWarning):
        repls = load_etf_replacements(user_path=user, etf_pairs=pairs)
    # Conflicting replacement must be filtered out (fail-soft).
    assert "VOO" not in repls.get("SPY", [])


def test_replacements_no_conflict_when_pairs_omitted() -> None:
    # When etf_pairs is None, no validation runs.
    repls = load_etf_replacements()
    assert isinstance(repls, dict)
