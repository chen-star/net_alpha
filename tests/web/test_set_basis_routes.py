"""HTTP tests for the inline set-basis routes."""
from __future__ import annotations

import datetime as dt

from fastapi.testclient import TestClient


def test_post_set_basis_single_persists_date_and_basis(client: TestClient, repo, seed_transfer_in) -> None:
    sym, account_id, trade_id, qty, xfer_date = seed_transfer_in
    resp = client.post(
        "/audit/set-basis/single",
        params={"caller": "pane"},
        data={
            "trade_id": trade_id,
            "cost_basis": "1500.00",
            "acquisition_date": "2024-03-12",
        },
    )
    assert resp.status_code == 200, resp.text
    refreshed = repo.get_trade_by_id(int(trade_id))
    assert refreshed.cost_basis == 1500.00
    assert refreshed.basis_source == "user_set"
    assert refreshed.date == dt.date(2024, 3, 12)


def test_post_set_basis_single_rejects_future_acquisition_date(client: TestClient, seed_transfer_in) -> None:
    _, _, trade_id, _, _ = seed_transfer_in
    future = (dt.date.today() + dt.timedelta(days=1)).isoformat()
    resp = client.post(
        "/audit/set-basis/single",
        params={"caller": "pane"},
        data={
            "trade_id": trade_id,
            "cost_basis": "1500.00",
            "acquisition_date": future,
        },
    )
    assert resp.status_code == 400
    assert "future" in resp.text.lower()


def test_post_set_basis_single_rejects_date_after_transfer(client: TestClient, seed_transfer_in) -> None:
    _, _, trade_id, _, xfer_date = seed_transfer_in
    after = (xfer_date + dt.timedelta(days=1)).isoformat()
    resp = client.post(
        "/audit/set-basis/single",
        params={"caller": "pane"},
        data={
            "trade_id": trade_id,
            "cost_basis": "1500.00",
            "acquisition_date": after,
        },
    )
    assert resp.status_code == 400
    assert "before transfer" in resp.text.lower() or "after transfer" in resp.text.lower()


def test_post_set_basis_single_rejects_negative_basis(client: TestClient, seed_transfer_in) -> None:
    _, _, trade_id, _, _ = seed_transfer_in
    resp = client.post(
        "/audit/set-basis/single",
        params={"caller": "pane"},
        data={
            "trade_id": trade_id,
            "cost_basis": "-50.00",
            "acquisition_date": "2024-03-12",
        },
    )
    assert resp.status_code == 400


def test_post_set_basis_legacy_path_still_works(client: TestClient, seed_transfer_in) -> None:
    """Legacy callers (timeline cell, drawer row) still post to /audit/set-basis."""
    _, _, trade_id, _, _ = seed_transfer_in
    resp = client.post(
        "/audit/set-basis",
        params={"caller": "timeline"},
        data={"trade_id": trade_id, "cost_basis": "999.99"},
    )
    assert resp.status_code == 200
