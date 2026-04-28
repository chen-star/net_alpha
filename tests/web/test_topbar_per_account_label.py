"""Task 23: topbar switcher label reflects the current request's account filter."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.models.preferences import AccountPreference
from net_alpha.web.app import create_app


def test_topbar_label_reflects_filter_account(tmp_path):
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    repo = Repository(engine)
    a = repo.get_or_create_account("Schwab", "Tax")
    b = repo.get_or_create_account("Schwab", "Roth")
    now = datetime(2026, 4, 27, tzinfo=UTC)
    repo.upsert_user_preference(
        AccountPreference(account_id=a.id, profile="conservative", density="comfortable", updated_at=now)
    )
    repo.upsert_user_preference(
        AccountPreference(account_id=b.id, profile="options", density="comfortable", updated_at=now)
    )
    client = TestClient(create_app(settings))

    # All accounts: profiles disagree -> "active" fallback
    all_html = client.get("/holdings").text
    assert ">active<" in all_html.lower()

    # Filter to Roth -> "options" label
    roth_html = client.get("/holdings", params={"account": "Schwab/Roth"}).text
    assert ">options<" in roth_html.lower()
