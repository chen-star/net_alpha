from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.web.app import create_app


def test_create_app_with_demo_mode_sets_state(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    app = create_app(settings, demo_mode=True)
    with TestClient(app):
        assert app.state.demo_mode is True


def test_create_app_default_demo_mode_false(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    app = create_app(settings)
    with TestClient(app):
        assert app.state.demo_mode is False
