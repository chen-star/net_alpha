"""End-to-end verification pipeline test.

Exercises the full chain:

  1. Trade CSV upload (Schwab) → trades + lots + wash-sale recompute
  2. Schwab All-Positions CSV upload → broker_position rows + implicit
     verify run via the /imports/positions handler
  3. Manual /verify/run → second verify run
  4. /verify page renders the latest run summary
  5. / and /positions both ship the verify-badge hx-get slot

This is the "all the pieces hang together" check; per-route fragments are
covered by tests/web/test_verify_*, tests/web/test_positions_csv_upload.py,
and tests/verify/*.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.web.app import create_app

# Match the conftest pattern: skip scheduler in tests so AsyncIOScheduler
# doesn't try to bind to a missing event loop.
os.environ.setdefault("NETALPHA_SKIP_SCHEDULER", "1")


TRADE_FIXTURE = Path(__file__).parents[1] / "fixtures" / "schwab_sample.csv"
POS_FIXTURE = Path(__file__).parents[1] / "verify" / "golden" / "cases" / "schwab_positions_sample.csv"


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    settings = Settings(data_dir=tmp_path)
    # Make sure schema migrations are applied to the temp DB so the
    # broker_position / verify_run tables exist before any route hits them.
    init_db(get_engine(settings.db_path))
    app = create_app(settings)
    return TestClient(app, raise_server_exceptions=False)


def test_full_pipeline_trade_import_then_positions_import_then_verify(client: TestClient) -> None:
    # 1) Trade CSV import. Uses the existing Schwab fixture so we exercise
    #    the real parser → trade-insert → wash-sale-recompute path.
    assert TRADE_FIXTURE.exists(), f"missing trade fixture: {TRADE_FIXTURE}"
    with TRADE_FIXTURE.open("rb") as f:
        r = client.post(
            "/imports",
            files=[("files", ("schwab_sample.csv", f, "text/csv"))],
            data={"account": "e2e-test"},
            follow_redirects=False,
        )
    # 303 = success redirect (to /imports/success?id=...).
    # 400 would mean parser rejection; anything else is a server bug.
    assert r.status_code in (200, 303), f"trade import unexpected status {r.status_code}: {r.text[:300]}"

    # 2) Positions CSV upload. The handler triggers a best-effort verify
    #    run inline (see web/routes/imports.py::upload_positions_csv).
    assert POS_FIXTURE.exists(), f"missing positions fixture: {POS_FIXTURE}"
    with POS_FIXTURE.open("rb") as f:
        r = client.post(
            "/imports/positions",
            files={"file": ("positions.csv", f, "text/csv")},
            follow_redirects=False,
        )
    assert r.status_code in (200, 303), f"positions upload unexpected status {r.status_code}: {r.text[:300]}"

    # 3) Manual verify run via the dedicated route.
    r = client.post("/verify/run", follow_redirects=False)
    assert r.status_code in (200, 303), f"verify/run unexpected status {r.status_code}: {r.text[:300]}"

    # 4) /verify page surfaces the latest run summary.
    r = client.get("/verify")
    assert r.status_code == 200
    assert "Latest run" in r.text, "verify page didn't render the latest-run summary section"

    # 5) Overview & Positions pages ship the verify-badge slot. The actual
    #    badge HTML is hx-get-loaded on the client; the page-side contract
    #    is just "the slot is present with the data-verify-badge marker is
    #    served by /verify/badge".
    for path in ("/", "/positions"):
        r = client.get(path)
        assert r.status_code == 200, f"{path} returned {r.status_code}"
        # Either the inline slot div or the rendered badge — both carry the
        # marker via either the hx-get URL or the data-verify-badge attribute.
        assert "verify/badge" in r.text or "data-verify-badge" in r.text, (
            f"{path} is missing the verify-badge slot/marker"
        )

    # 6) The /verify/badge endpoint itself renders a real badge with the
    #    data-verify-badge attribute, given at least one run has happened.
    r = client.get("/verify/badge?page=overview")
    assert r.status_code == 200
    assert "data-verify-badge" in r.text, "verify/badge fragment missing data attribute"
