from fastapi.testclient import TestClient


def test_top_movers_panel_omitted_when_no_open_positions(client: TestClient):
    """When there are no positions, the Top Movers row template renders empty.
    The outer row wrapper still ships (so Edit layout can manage it), but the
    panel itself (with its <h3>Top movers</h3> header) is not present."""
    body = client.get("/portfolio/body?period=ytd").text
    # The actual top-movers panel header (<h4>Top movers</h4>) must NOT
    # appear when empty. The row wrapper / Edit-layout placeholder may exist.
    assert "Top movers</h4>" not in body
