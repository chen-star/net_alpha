from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.web.app import create_app
from net_alpha.web.dependencies import effective_db_path


def test_effective_db_path_real_when_demo_mode_false(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    assert effective_db_path(settings, demo_mode=False) == tmp_path / "net_alpha.db"


def test_effective_db_path_demo_when_demo_mode_true(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    assert effective_db_path(settings, demo_mode=True) == tmp_path / "demo.db"


def test_app_starts_with_demo_mode_false(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    app = create_app(settings)
    with TestClient(app):
        assert app.state.demo_mode is False
