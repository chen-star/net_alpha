"""Live-server fixtures for end-to-end Playwright tests against the multi-account UI.

Boots the FastAPI app on a free localhost port using an ISOLATED tmp_path
data dir, seeded with multiple accounts. Avoids the schema-mismatch issue
with the user's real ~/.net_alpha/ database.

``build_demo_db`` seeds two accounts: ``schwab/taxable`` and ``schwab/ira``
(confirmed by reading ``src/net_alpha/web/demo/fixture.py``), so multi-account
filtering tests can run unconditionally.
"""

from __future__ import annotations

import os
import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
import uvicorn

from net_alpha.config import Settings
from net_alpha.web.app import create_app

# Same env guard as tests/web/conftest.py: skip the AsyncIO scheduler that
# isn't compatible with sync test environments.
os.environ.setdefault("NETALPHA_SKIP_SCHEDULER", "1")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def seeded_data_dir(tmp_path_factory) -> Path:
    """An isolated data dir with the demo DB seeded (two accounts: taxable + ira).

    Also writes one ``AccountPreference`` row so the profile-picker modal
    (shown when accounts exist but no prefs do) does not intercept pointer
    events during Playwright clicks.
    """
    from datetime import datetime

    data_dir = tmp_path_factory.mktemp("e2e_data")
    settings = Settings(data_dir=data_dir)
    from net_alpha.db.connection import get_engine
    from net_alpha.db.repository import Repository
    from net_alpha.models.preferences import AccountPreference
    from net_alpha.web.demo import build_demo_db

    build_demo_db(settings.db_path)

    # Suppress the first-visit profile picker by writing a preference for
    # the first account; the modal only appears when prefs is empty.
    engine = get_engine(settings.db_path)
    repo = Repository(engine)
    accounts = repo.list_accounts()
    if accounts:
        repo.upsert_user_preference(
            AccountPreference(
                account_id=accounts[0].id,
                profile="active",
                density="comfortable",
                theme="system",
                updated_at=datetime.now(),
            )
        )
    return data_dir


@pytest.fixture(scope="module")
def live_server_seeded(seeded_data_dir: Path) -> Iterator[str]:
    """Boot the app against the seeded isolated data dir; yield the base URL."""
    port = _free_port()
    settings = Settings(data_dir=seeded_data_dir)
    app = create_app(settings)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                break
        except OSError:
            time.sleep(0.1)
    else:
        server.should_exit = True
        raise RuntimeError("live_server_seeded did not start within 5 s")

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=2.0)


@pytest.fixture(scope="session")
def browser_context_args():
    return {
        "viewport": {"width": 1440, "height": 900},
        "device_scale_factor": 1,
        "color_scheme": "dark",
    }
