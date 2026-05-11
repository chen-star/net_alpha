"""Tests for the /imports/positions CSV upload endpoint.

The endpoint ingests a Schwab All-Positions CSV (parsed by
``net_alpha.import_.positions_csv``) and persists it as an ImportRecord +
broker_position rows. A subsequent ``latest_broker_positions()`` call
must surface those rows.
"""

from __future__ import annotations

from pathlib import Path

FIXTURE = Path(__file__).parents[1] / "verify" / "golden" / "cases" / "schwab_positions_sample.csv"


def test_positions_csv_upload_creates_import_record_and_broker_position_rows(client, repo):
    """POST /imports/positions returns success and persists broker_position rows."""
    with FIXTURE.open("rb") as f:
        resp = client.post(
            "/imports/positions",
            files={"file": ("positions.csv", f, "text/csv")},
            follow_redirects=False,
        )
    assert resp.status_code in (200, 303)

    # Verify rows were saved via the repository.
    rows, as_of = repo.latest_broker_positions()
    assert as_of == "2026-05-10"
    assert len(rows) == 3
    symbols = {r.symbol for r in rows}
    assert symbols == {"AAPL", "MSFT", "VOO"}


def test_positions_csv_upload_surfaces_on_imports_page(client):
    """The new import row appears on the imports legacy page (lazy-loaded body)."""
    with FIXTURE.open("rb") as f:
        client.post(
            "/imports/positions",
            files={"file": ("positions.csv", f, "text/csv")},
            follow_redirects=False,
        )
    # The drawer entry lazy-loads /imports/_legacy_page via HTMX — that's
    # where the actual imports table lives. The csv_filename is stamped
    # ``[positions] as of <date>`` so the row is unambiguously a positions
    # import (no ``kind`` column on the imports table).
    list_resp = client.get("/imports/_legacy_page")
    assert list_resp.status_code == 200
    assert "[positions]" in list_resp.text
    assert "2026-05-10" in list_resp.text
    assert "positions" in list_resp.text.lower()


def test_latest_broker_positions_empty_on_fresh_db(repo):
    """A freshly initialized DB returns an empty list + None."""
    rows, as_of = repo.latest_broker_positions()
    assert rows == []
    assert as_of is None
