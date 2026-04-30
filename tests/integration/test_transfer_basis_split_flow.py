"""End-to-end: import → render positions pane → submit multi-lot split →
re-render → assert the row is no longer in basis-missing state and N
siblings exist with correct dates/qtys/basises."""

from __future__ import annotations

import datetime as dt

from fastapi.testclient import TestClient


def test_multi_lot_split_flow_clears_basis_warning(client: TestClient, repo, seed_transfer_in) -> None:
    sym, account_id, trade_id, qty, xfer_date = seed_transfer_in

    # 1. Initial pane renders the single-lot form (basis missing).
    resp = client.get("/positions/pane", params={"sym": sym, "account_id": account_id})
    assert resp.status_code == 200
    assert "Set basis" in resp.text
    assert f"/audit/set-basis/multi/{trade_id}" in resp.text

    # 2. Switch to multi-lot fragment.
    resp = client.get(f"/audit/set-basis/multi/{trade_id}")
    assert resp.status_code == 200
    assert "Sum of qty" in resp.text

    # 3. Submit a 3-lot split (25 + 25 + 50 = 100).
    resp = client.post(
        "/audit/set-basis/multi",
        params={"caller": "pane"},
        data={
            "trade_id": trade_id,
            "dates": ["2024-03-12", "2024-09-04", "2025-01-08"],
            "quantities": ["25", "25", "50"],
            "basises": ["1875.00", "2150.50", "4900.00"],
        },
    )
    assert resp.status_code == 200, resp.text
    assert "saved" in resp.text.lower() or "Saved" in resp.text

    # 4. Verify three sibling Trade rows now exist.
    parent = repo.get_trade_by_id(int(trade_id))
    siblings = repo.get_trades_in_transfer_group(parent.transfer_group_id)
    assert len(siblings) == 3
    by_date = {s.date: s for s in siblings}
    assert by_date[dt.date(2024, 3, 12)].quantity == 25.0
    assert by_date[dt.date(2024, 3, 12)].cost_basis == 1875.00
    assert by_date[dt.date(2024, 9, 4)].quantity == 25.0
    assert by_date[dt.date(2024, 9, 4)].cost_basis == 2150.50
    assert by_date[dt.date(2025, 1, 8)].quantity == 50.0
    assert by_date[dt.date(2025, 1, 8)].cost_basis == 4900.00
    # Parent row's basis_unknown should be cleared too (hygiene-checker correctness).
    assert parent.basis_unknown is False

    # 5. Re-render the pane: the basis-missing warning is gone.
    resp = client.get("/positions/pane", params={"sym": sym, "account_id": account_id})
    assert resp.status_code == 200
    # The "Set basis" panel should not render when no transfer-in lot lacks basis.
    # (compute_positions sets basis_known=True once any lot has cost_basis != 0.)
    assert "Set basis &amp; date" not in resp.text and "Set basis & date" not in resp.text
