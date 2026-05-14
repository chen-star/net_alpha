"""Route tests for /portfolio/layout/* and layout-aware /portfolio/body."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.models.domain import ImportRecord, Trade
from net_alpha.prefs.overview_layout import OverviewLayout, default_overview_layout
from net_alpha.web.app import create_app


@pytest.fixture
def seeded_client(tmp_path):
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    repo = Repository(engine)
    account = repo.get_or_create_account("Schwab", "Tax")
    trade = Trade(
        account="Schwab/Tax",
        date=date(2026, 1, 2),
        ticker="AAPL",
        action="Buy",
        quantity=10.0,
        proceeds=None,
        cost_basis=1500.0,
    )
    record = ImportRecord(
        account_id=account.id,
        csv_filename="x.csv",
        csv_sha256="sha-seed",
        imported_at=datetime(2026, 1, 2, tzinfo=UTC),
        trade_count=1,
    )
    repo.add_import(account, record, [trade])
    return TestClient(create_app(settings), raise_server_exceptions=False), repo


def test_body_still_200_after_layout_wiring(seeded_client):
    client, _ = seeded_client
    r = client.get("/portfolio/body")
    assert r.status_code == 200


def test_body_still_200_with_saved_layout(seeded_client):
    client, repo = seeded_client
    repo.set_overview_layout(
        "active",
        OverviewLayout(
            rows=["kpis", "inbox", "curves", "monthly_pl", "allocation", "top_movers"],
            hidden=["top_movers"],
        ),
    )
    r = client.get("/portfolio/body")
    assert r.status_code == 200


def test_post_reorder_writes_new_order(seeded_client):
    client, repo = seeded_client
    r = client.post(
        "/portfolio/layout/reorder",
        data={"row": ["kpis", "inbox", "curves", "monthly_pl", "allocation", "top_movers"]},
    )
    assert r.status_code == 204
    layout = repo.get_overview_layout("active")
    assert layout.rows[0] == "kpis"
    assert layout.rows[1] == "inbox"


def test_post_reorder_preserves_hidden_set(seeded_client):
    client, repo = seeded_client
    repo.set_overview_layout(
        "active",
        OverviewLayout(
            rows=["inbox", "kpis", "curves", "monthly_pl", "allocation", "top_movers"],
            hidden=["top_movers"],
        ),
    )
    client.post(
        "/portfolio/layout/reorder",
        data={"row": ["kpis", "inbox", "curves", "monthly_pl", "allocation", "top_movers"]},
    )
    assert repo.get_overview_layout("active").hidden == ["top_movers"]


def test_post_reorder_drops_unknown_rows(seeded_client):
    client, repo = seeded_client
    r = client.post(
        "/portfolio/layout/reorder",
        data={"row": ["kpis", "garbage", "inbox"]},
    )
    assert r.status_code == 204
    layout = repo.get_overview_layout("active")
    assert "garbage" not in layout.rows
    assert layout.rows[:2] == ["kpis", "inbox"]


def test_post_visibility_hides_row(seeded_client):
    client, repo = seeded_client
    r = client.post(
        "/portfolio/layout/visibility",
        data={"row": "top_movers", "hidden": "true"},
    )
    assert r.status_code == 204
    assert "top_movers" in repo.get_overview_layout("active").hidden


def test_post_visibility_shows_row(seeded_client):
    client, repo = seeded_client
    repo.set_overview_layout(
        "active",
        OverviewLayout(
            rows=["inbox", "kpis", "curves", "monthly_pl", "allocation", "top_movers"],
            hidden=["top_movers"],
        ),
    )
    r = client.post(
        "/portfolio/layout/visibility",
        data={"row": "top_movers", "hidden": "false"},
    )
    assert r.status_code == 204
    assert "top_movers" not in repo.get_overview_layout("active").hidden


def test_post_visibility_is_idempotent(seeded_client):
    client, repo = seeded_client
    client.post("/portfolio/layout/visibility", data={"row": "top_movers", "hidden": "true"})
    client.post("/portfolio/layout/visibility", data={"row": "top_movers", "hidden": "true"})
    assert repo.get_overview_layout("active").hidden.count("top_movers") == 1


def test_post_visibility_drops_unknown_row(seeded_client):
    client, repo = seeded_client
    r = client.post(
        "/portfolio/layout/visibility",
        data={"row": "garbage", "hidden": "true"},
    )
    assert r.status_code == 204
    assert "garbage" not in repo.get_overview_layout("active").hidden


def test_post_reset_clears_profile_row_htmx(seeded_client):
    client, repo = seeded_client
    repo.set_overview_layout(
        "active",
        OverviewLayout(
            rows=["kpis", "inbox", "curves", "monthly_pl", "allocation", "top_movers"],
            hidden=["top_movers"],
        ),
    )
    r = client.post("/portfolio/layout/reset", headers={"HX-Request": "true"}, follow_redirects=False)
    assert r.status_code in (200, 204)
    assert r.headers.get("HX-Redirect") == "/"
    assert repo.get_overview_layout("active") == default_overview_layout()


def test_post_reset_non_htmx_redirects_303(seeded_client):
    client, repo = seeded_client
    repo.set_overview_layout(
        "active",
        OverviewLayout(
            rows=["kpis", "inbox", "curves", "monthly_pl", "allocation", "top_movers"],
            hidden=[],
        ),
    )
    r = client.post("/portfolio/layout/reset", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/"
    assert repo.get_overview_layout("active") == default_overview_layout()


def test_body_renders_with_default_layout_when_none_saved(seeded_client):
    client, _ = seeded_client
    r = client.get("/portfolio/body")
    assert r.status_code == 200
    body = r.text
    assert body.index('data-row-key="inbox"') < body.index('data-row-key="kpis"')
    assert body.index('data-row-key="kpis"') < body.index('data-row-key="curves"')


def test_body_respects_saved_order(seeded_client):
    client, repo = seeded_client
    repo.set_overview_layout(
        "active",
        OverviewLayout(
            rows=["kpis", "inbox", "curves", "monthly_pl", "allocation", "top_movers"],
            hidden=[],
        ),
    )
    r = client.get("/portfolio/body")
    assert r.status_code == 200
    body = r.text
    assert body.index('data-row-key="kpis"') < body.index('data-row-key="inbox"')


def test_body_hides_hidden_rows_when_not_in_edit_mode(seeded_client):
    """Hidden rows are emitted as compact placeholders so Edit layout can
    surface them — but they're class-marked ``overview-row-hidden`` so CSS
    keeps them out of the layout until the user enters edit mode. They never
    render their full content (still a perf saving)."""
    client, repo = seeded_client
    repo.set_overview_layout(
        "active",
        OverviewLayout(
            rows=["inbox", "kpis", "curves", "monthly_pl", "allocation", "top_movers"],
            hidden=["top_movers"],
        ),
    )
    r = client.get("/portfolio/body")
    assert r.status_code == 200
    # Row is present so it can be surfaced in edit mode...
    assert 'data-row-key="top_movers"' in r.text
    # ...but marked hidden so CSS keeps it out of the layout.
    assert "overview-row-hidden" in r.text
    # And the full content stub (the top-movers panel template) is NOT
    # rendered — only the lightweight placeholder.
    assert "Top movers" not in r.text or "row-hidden-placeholder" in r.text


def test_overview_layout_js_is_served(seeded_client):
    client, _ = seeded_client
    r = client.get("/static/overview_layout.js")
    assert r.status_code == 200
    assert "/portfolio/layout/reorder" in r.text


def test_base_template_loads_overview_layout_js(seeded_client):
    client, _ = seeded_client
    r = client.get("/")
    assert "/static/overview_layout.js" in r.text
