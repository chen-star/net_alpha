from __future__ import annotations

import pytest

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository


@pytest.fixture
def repo(tmp_path) -> Repository:
    """A clean Repository backed by a tmp_path SQLite DB."""
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    return Repository(engine)


@pytest.fixture
def schwab_account(repo: Repository):
    """A pre-created Schwab account row for tests that need an account_id."""
    return repo.get_or_create_account(broker="Schwab", label="Tax")
