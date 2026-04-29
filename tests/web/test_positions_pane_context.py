"""The positions pane must always pass transfer context (trade_id,
transfer_qty, transfer_date) so the inline set-basis form can validate
multi-lot splits."""
from __future__ import annotations

import datetime as dt

from fastapi.testclient import TestClient


def test_positions_pane_renders_transfer_context_for_transfer_in(client: TestClient, seed_transfer_in) -> None:
    """When a position has a transfer_in trade with no basis, the rendered
    pane HTML must contain the trade_id, the transferred qty, and the
    transfer date so the multi-lot fragment can validate against them."""
    sym, account_id, trade_id, qty, xfer_date = seed_transfer_in
    resp = client.get(f"/portfolio/positions-pane/{sym}", params={"account_id": account_id})
    assert resp.status_code == 200
    html = resp.text
    assert f'value="{trade_id}"' in html, "single-lot form should expose trade_id"
    # transfer-related attributes used by the multi-lot form for validation:
    assert f'data-transfer-qty="{qty}"' in html
    assert f'data-transfer-date="{xfer_date.isoformat()}"' in html
