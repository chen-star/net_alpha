from __future__ import annotations

from pathlib import Path

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository


def _real_repo(tmp_path: Path) -> Repository:
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    return Repository(engine)


def test_tour_completed_defaults_false(tmp_path: Path) -> None:
    repo = _real_repo(tmp_path)
    assert repo.get_tour_completed() is False


def test_set_tour_completed_persists(tmp_path: Path) -> None:
    repo = _real_repo(tmp_path)
    repo.set_tour_completed(True)
    assert repo.get_tour_completed() is True
    repo.set_tour_completed(False)
    assert repo.get_tour_completed() is False
