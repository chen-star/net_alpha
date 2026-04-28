"""Fixtures for Playwright-driven snapshot tests.

These tests boot the FastAPI app on a free localhost port in a background
thread so a real browser can navigate to it. Database is the user's normal
~/.net_alpha/net_alpha.db — Phase 0 baselines must be captured against
real data, not an empty DB. This is intentional: snapshots are a regression
guard for the developer's working DB, not a CI-isolated test.

Run only on demand:
    uv run pytest tests/web/snapshots -v

Skip in routine `make test`:
    uv run pytest --ignore=tests/web/snapshots
"""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator

import pytest
import uvicorn

from net_alpha.config import Settings
from net_alpha.web.app import create_app


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def live_server() -> Iterator[str]:
    """Boot the app on a free port; yield the base URL; shut down on teardown."""
    port = _free_port()
    settings = Settings()
    app = create_app(settings)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    # Wait until the server is accepting connections (max 5 s).
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                break
        except OSError:
            time.sleep(0.1)
    else:
        server.should_exit = True
        raise RuntimeError("live_server did not start within 5 s")

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=2.0)


@pytest.fixture(scope="session")
def browser_context_args():
    """Lock viewport + device pixel ratio so screenshots are deterministic."""
    return {
        "viewport": {"width": 1440, "height": 900},
        "device_scale_factor": 1,
        "color_scheme": "dark",
    }


def pytest_addoption(parser):  # noqa: D401 — pytest hook
    """Add `--update-snapshots` flag.

    Lives in conftest.py because pytest only discovers `pytest_addoption`
    from conftest files (and rootdir plugins), not from individual test
    modules.
    """
    parser.addoption(
        "--update-snapshots",
        action="store_true",
        default=False,
        help="Overwrite baseline snapshots instead of comparing.",
    )
