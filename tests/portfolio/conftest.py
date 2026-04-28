"""Shared fixtures for portfolio.tax_planner tests."""

from __future__ import annotations

import pytest

from tests.audit.conftest import repo as _repo
from tests.audit.conftest import schwab_account as _schwab_account
from tests.audit.conftest import seed_import as _seed_import_impl

# Re-export fixtures
repo = _repo
schwab_account = _schwab_account


@pytest.fixture
def seed_import():
    """Fixture wrapper for seed_import helper (it's a plain function in audit.conftest)."""
    return _seed_import_impl


__all__ = ["repo", "schwab_account", "seed_import"]
