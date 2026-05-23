"""POST /portfolio/layout/reorder must respect the per-account profile scope
(audit #17).

Before the fix the JS posted only `row=` keys — no `?account=` and no `Referer`
fallback — so the route always resolved to the taxpayer-level default profile
even when the user was reordering on a per-account Overview. The fix accepts
the account in three ways (form body, query string, Referer header) so old
cached JS, the new explicit form, and direct API calls all land on the right
profile bucket.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.models.preferences import AccountPreference
from net_alpha.web.app import create_app


@pytest.fixture
def repo_client(tmp_path):
    """Repository + client wired to a temp DB with two accounts having
    different profiles. The brokerage account is ``conservative`` and the IRA
    is ``options``; their mixed All-accounts consensus is ``active`` (default).
    This three-way distinction makes it possible to assert which profile
    bucket a reorder POST landed in.
    """
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    repo = Repository(engine)
    brokerage = repo.get_or_create_account("schwab", "Brokerage")
    ira = repo.get_or_create_account("schwab", "IRA")
    repo.upsert_user_preference(
        AccountPreference(
            account_id=brokerage.id,
            profile="conservative",
            density="comfortable",
            theme="system",
            updated_at=datetime.now(UTC),
        )
    )
    repo.upsert_user_preference(
        AccountPreference(
            account_id=ira.id,
            profile="options",
            density="comfortable",
            theme="system",
            updated_at=datetime.now(UTC),
        )
    )
    client = TestClient(create_app(settings), raise_server_exceptions=False)
    return repo, client, ira


_ROWS = ["kpis", "inbox", "curves", "monthly_pl", "allocation", "top_movers"]


def test_reorder_with_query_string_account_writes_to_per_account_profile(repo_client):
    """When ``?account=schwab/IRA`` is on the URL the route must scope writes
    to the IRA's profile (``options``), not the taxpayer-level ``active``."""
    repo, client, _ = repo_client
    body = "&".join(f"row={r}" for r in _ROWS)
    res = client.post(
        "/portfolio/layout/reorder?account=schwab/IRA",
        content=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res.status_code == 204
    # IRA's profile (options) got the write; the taxpayer-level (active) did not.
    assert repo.get_overview_layout("options").rows == _ROWS
    from net_alpha.prefs.overview_layout import default_overview_layout

    assert repo.get_overview_layout("active") == default_overview_layout()


def test_reorder_with_referer_fallback_writes_to_per_account_profile(repo_client):
    """No ``?account=`` on the POST, no form-body ``account``, but a Referer
    header that carries ``?account=schwab/IRA`` — the route must parse it and
    still scope to the IRA's profile (covers old cached JS)."""
    repo, client, _ = repo_client
    body = "&".join(f"row={r}" for r in _ROWS)
    res = client.post(
        "/portfolio/layout/reorder",
        content=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "http://testserver/?account=schwab/IRA",
        },
    )
    assert res.status_code == 204
    assert repo.get_overview_layout("options").rows == _ROWS
    from net_alpha.prefs.overview_layout import default_overview_layout

    assert repo.get_overview_layout("active") == default_overview_layout()


def test_reorder_with_no_account_anywhere_falls_back_to_taxpayer_profile(repo_client):
    """No ``?account=``, no Referer fallback — the historical behavior: the
    consensus profile (``active``, since the two prefs disagree) gets the
    write."""
    repo, client, _ = repo_client
    body = "&".join(f"row={r}" for r in _ROWS)
    res = client.post(
        "/portfolio/layout/reorder",
        content=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res.status_code == 204
    # Mixed prefs → consensus falls to ``active`` (the taxpayer-level default).
    assert repo.get_overview_layout("active").rows == _ROWS
    from net_alpha.prefs.overview_layout import default_overview_layout

    assert repo.get_overview_layout("options") == default_overview_layout()


def test_overview_layout_js_includes_account_from_url(repo_client):
    """The new client-side JS must thread current-page ``?account=`` values
    into the POST body, not just ``row=`` keys."""
    _, client, _ = repo_client
    r = client.get("/static/overview_layout.js")
    assert r.status_code == 200
    js = r.text
    # The JS must reference window.location.search and the account param.
    assert "window.location.search" in js
    assert "account" in js
