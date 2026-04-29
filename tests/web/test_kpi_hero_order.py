import re
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.models.preferences import AccountPreference
from net_alpha.web.app import create_app


def _seed(tmp_path, profile_label):
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    repo = Repository(engine)
    a = repo.get_or_create_account("Schwab", "Tax")
    repo.upsert_user_preference(
        AccountPreference(
            account_id=a.id,
            profile=profile_label,
            density="comfortable",
            updated_at=datetime(2026, 4, 27, tzinfo=UTC),
        )
    )
    app = create_app(settings)
    return TestClient(app)


def _kpi_slot_order(html: str) -> list[str]:
    """Return the order of `data-kpi-slot` attribute values as they appear."""
    return re.findall(r'data-kpi-slot="([^"]+)"', html)


def test_kpi_order_conservative(tmp_path):
    """Phase 3 C3: fixed 3+4 grid — profile no longer changes slot order."""
    client = _seed(tmp_path, "conservative")
    html = client.get("/portfolio/kpis", params={"account": "Schwab/Tax"}).text
    order = _kpi_slot_order(html)
    assert order[:3] == ["hero", "today", "cash"]
    assert order[3:] == ["realized", "unrealized", "contributed", "growth"]


def test_kpi_order_active(tmp_path):
    """Phase 3 C3: fixed 3+4 grid — profile no longer changes slot order."""
    client = _seed(tmp_path, "active")
    html = client.get("/portfolio/kpis", params={"account": "Schwab/Tax"}).text
    order = _kpi_slot_order(html)
    # Fixed layout: hero + today + cash (top) + 4 small (bottom)
    assert order[:3] == ["hero", "today", "cash"]
    assert order[3:] == ["realized", "unrealized", "contributed", "growth"]
    # wash_impact removed from Portfolio KPI grid entirely (lives on /tax).
    assert "wash_impact" not in order


def test_kpi_order_options(tmp_path):
    """Phase 3 C3: fixed 3+4 grid — profile no longer changes slot order."""
    client = _seed(tmp_path, "options")
    html = client.get("/portfolio/kpis", params={"account": "Schwab/Tax"}).text
    order = _kpi_slot_order(html)
    assert order[:3] == ["hero", "today", "cash"]
    assert order[3:] == ["realized", "unrealized", "contributed", "growth"]
    assert "wash_impact" not in order
