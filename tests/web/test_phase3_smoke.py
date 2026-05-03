# tests/web/test_phase3_smoke.py
"""Phase 3 end-to-end smoke — profiles, switcher, density toggle.

Bootstraps the app with two accounts and matching preferences. Hits every
page and asserts the switcher label, default-tab routing, density toggle,
and KPI ordering all reflect the per-account profile.
"""

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.models.preferences import AccountPreference
from net_alpha.web.app import create_app


def test_phase3_smoke(tmp_path):
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    repo = Repository(engine)

    tax_acct = repo.get_or_create_account("Schwab", "Tax")
    roth_acct = repo.get_or_create_account("Schwab", "Roth")
    now = datetime(2026, 4, 27, tzinfo=UTC)
    repo.upsert_user_preference(
        AccountPreference(account_id=tax_acct.id, profile="active", density="comfortable", updated_at=now)
    )
    repo.upsert_user_preference(
        AccountPreference(account_id=roth_acct.id, profile="options", density="tax", updated_at=now)
    )

    client = TestClient(create_app(settings))

    # 1. The first-visit modal is gone (prefs exist).
    assert "Pick a default profile per account" not in client.get("/").text

    # 2. /tax with active filter -> default tab wash-sales (Phase 1 IA: harvest moved to /positions?view=at-loss).
    tax_resp = client.get("/tax", params={"account": "Schwab/Tax"}).text
    assert 'data-active-tab="wash-sales"' in tax_resp

    # 3. /tax with conservative would default to wash-sales — but we don't have
    #    a conservative account, so flip Roth temporarily.
    repo.upsert_user_preference(
        AccountPreference(account_id=roth_acct.id, profile="conservative", density="comfortable", updated_at=now)
    )
    cons_tax = client.get("/tax", params={"account": "Schwab/Roth"}).text
    assert 'data-active-tab="wash-sales"' in cons_tax
    # Restore Roth -> options for the rest of the test.
    repo.upsert_user_preference(
        AccountPreference(account_id=roth_acct.id, profile="options", density="tax", updated_at=now)
    )

    # 4. /holdings with options + tax density -> tax-density columns visible.
    holdings_roth = client.get("/holdings", params={"account": "Schwab/Roth"}).text
    assert 'data-col="lt_st_split"' in holdings_roth
    assert 'data-col="days_to_ltcg"' in holdings_roth  # tax density adds this
    # Phase 1 E1: per-page density toggle removed; drawer toggle uses page_key="/"
    assert 'data-page-key="/"' in holdings_roth

    # 5. /holdings with active + comfortable -> days_held + lt_st_split, no tax-only cols.
    holdings_tax = client.get("/holdings", params={"account": "Schwab/Tax"}).text
    assert 'data-col="days_held"' in holdings_tax
    assert 'data-col="days_to_ltcg"' not in holdings_tax

    # 6. KPI grid — hierarchy redesign: 1 hero + 1 promoted + 3 small.
    kpis = client.get("/portfolio/kpis", params={"account": "Schwab/Tax"}).text
    import re

    order = re.findall(r'data-kpi-slot="([^"]+)"', kpis)
    # Top row: hero + total_return. Bottom row: realized + unrealized + cash.
    # Net Contributed folded into Cash subtitle (no longer its own slot).
    assert order == ["hero", "total_return", "realized", "unrealized", "cash"]
    # wash_impact removed from Portfolio KPI grid entirely (lives on /tax).
    assert "wash_impact" not in order
    assert "contributed" not in order

    # 7. Topbar switcher form posts to /preferences with account_id.
    home = client.get("/").text
    assert 'hx-post="/preferences"' in home
    # 8. POST /preferences flips Tax to conservative; verify persistence.
    resp = client.post(
        "/preferences",
        data={"account_id": str(tax_acct.id), "profile": "conservative", "density": "comfortable"},
    )
    assert resp.status_code == 204
    assert resp.headers.get("hx-refresh") == "true"
    # Re-render /portfolio/kpis for Tax -> conservative; fixed layout unchanged.
    kpis2 = client.get("/portfolio/kpis", params={"account": "Schwab/Tax"}).text
    order2 = re.findall(r'data-kpi-slot="([^"]+)"', kpis2)
    assert order2 == ["hero", "total_return", "realized", "unrealized", "cash"]
