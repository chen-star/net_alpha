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
    """Hierarchy redesign: 1 hero + 1 promoted + 3 small.
    Top row: hero + total_return. Bottom row: realized + unrealized + cash.
    Net Contributed is folded into the Cash tile subtitle (no longer a slot)."""
    client = _seed(tmp_path, "conservative")
    html = client.get("/portfolio/kpis", params={"account": "Schwab/Tax"}).text
    order = _kpi_slot_order(html)
    assert order == ["hero", "total_return", "realized", "unrealized", "cash"]


def test_kpi_order_active(tmp_path):
    """Profile-independent hierarchy."""
    client = _seed(tmp_path, "active")
    html = client.get("/portfolio/kpis", params={"account": "Schwab/Tax"}).text
    order = _kpi_slot_order(html)
    assert order == ["hero", "total_return", "realized", "unrealized", "cash"]
    assert "today" not in order
    assert "growth" not in order
    assert "contributed" not in order  # folded into cash subtitle


def test_kpi_order_options(tmp_path):
    client = _seed(tmp_path, "options")
    html = client.get("/portfolio/kpis", params={"account": "Schwab/Tax"}).text
    order = _kpi_slot_order(html)
    assert order == ["hero", "total_return", "realized", "unrealized", "cash"]
    assert "wash_impact" not in order
