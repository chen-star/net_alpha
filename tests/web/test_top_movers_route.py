from datetime import date

from fastapi.testclient import TestClient

from net_alpha.db.repository import Repository
from net_alpha.models.domain import Trade


def test_top_movers_panel_omitted_when_no_open_positions(client: TestClient):
    body = client.get("/portfolio/body?period=ytd").text
    # Phrase used in the Top Movers header — should NOT appear when empty.
    assert "Top movers" not in body
