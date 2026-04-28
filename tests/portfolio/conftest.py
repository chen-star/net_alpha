"""Shared fixtures for portfolio.tax_planner tests."""

from __future__ import annotations

import pytest

from net_alpha.engine.detector import detect_in_window
from net_alpha.models.domain import Trade
from tests.audit.conftest import repo as _repo
from tests.audit.conftest import schwab_account as _schwab_account
from tests.audit.conftest import seed_import as _seed_import_impl

repo = _repo
schwab_account = _schwab_account


@pytest.fixture
def seed_import():
    """Fixture wrapper for seed_import helper (it's a plain function in audit.conftest)."""
    return _seed_import_impl


@pytest.fixture
def seed_lots():
    """Populate the lots table from the repo's existing trades via detect_in_window.

    Use after seed_import to make all_lots() return populated rows for the test.
    """

    def _seed_lots(repo, trades: list[Trade] | None = None) -> None:
        trades = trades if trades is not None else repo.all_trades()
        if not trades:
            return
        dates = [t.date for t in trades]
        result = detect_in_window(trades, min(dates), max(dates), etf_pairs={})
        repo.replace_lots_in_window(min(dates), max(dates), result.lots)

    return _seed_lots


__all__ = ["repo", "schwab_account", "seed_import", "seed_lots"]
