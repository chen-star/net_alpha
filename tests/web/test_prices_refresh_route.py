from __future__ import annotations

import datetime as dt
from decimal import Decimal
from unittest.mock import patch

from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.pricing.provider import Quote
from net_alpha.web.app import create_app


def _client(tmp_path):
    settings = Settings(data_dir=tmp_path)
    app = create_app(settings)
    return TestClient(app), app


def test_refresh_invalidates_and_refetches(tmp_path):
    client, app = _client(tmp_path)

    fake_quote = Quote(
        symbol="SPY",
        price=Decimal("460.5"),
        as_of=dt.datetime.now(dt.UTC),
        source="yahoo",
    )
    with patch.object(app.state.price_provider, "get_quotes", return_value={"SPY": fake_quote}) as mock:
        # Prime the cache once.
        client.post("/prices/refresh", params={"symbols": "SPY"})
        # Refresh again — should invalidate and refetch.
        response = client.post("/prices/refresh", params={"symbols": "SPY"})
        assert response.status_code == 200
        assert mock.call_count == 2


def test_refresh_with_no_symbols_returns_400(tmp_path):
    client, _ = _client(tmp_path)
    response = client.post("/prices/refresh")
    assert response.status_code == 400
