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


def test_post_set_basis_single_rejects_invalid_date_format(client, seed_transfer_in) -> None:
    _, _, trade_id, _, _ = seed_transfer_in
    resp = client.post(
        "/audit/set-basis/single",
        params={"caller": "pane"},
        data={
            "trade_id": trade_id,
            "cost_basis": "1000.00",
            "acquisition_date": "not-a-date",
        },
    )
    assert resp.status_code == 400
    assert "invalid date" in resp.text.lower()


def test_post_set_basis_single_returns_404_when_trade_missing(client, seed_transfer_in) -> None:
    # Using a numeric id that won't exist in this fresh test DB.
    resp = client.post(
        "/audit/set-basis/single",
        params={"caller": "pane"},
        data={
            "trade_id": "999999",
            "cost_basis": "1000.00",
            "acquisition_date": "2024-03-12",
        },
    )
    assert resp.status_code == 404
    assert "not found" in resp.text.lower()


def test_get_set_basis_multi_renders_row_table(client: TestClient, seed_transfer_in) -> None:
    sym, _, trade_id, qty, xfer_date = seed_transfer_in
    resp = client.get(f"/audit/set-basis/multi/{trade_id}")
    assert resp.status_code == 200
    html = resp.text
    # Header showing the constraint:
    assert f"{qty}" in html
    # At least one row of inputs:
    assert 'name="dates"' in html or 'name="dates[]"' in html
    assert 'name="quantities"' in html or 'name="quantities[]"' in html
    assert 'name="basises"' in html or 'name="basises[]"' in html
    # "Add lot" link and "Back to single lot" link:
    assert "Add lot" in html
    assert "Back to single lot" in html


def test_get_set_basis_single_renders_default_fragment(client: TestClient, seed_transfer_in) -> None:
    """The "Back" link in the multi-lot fragment GETs this route."""
    sym, _, trade_id, _, _ = seed_transfer_in
    resp = client.get(f"/audit/set-basis/single/{trade_id}")
    assert resp.status_code == 200
    html = resp.text
    assert 'name="acquisition_date"' in html
    assert 'name="cost_basis"' in html
    assert "Split into multiple lots" in html


def test_single_lot_fragment_includes_split_link(client: TestClient, seed_transfer_in) -> None:
    sym, _, trade_id, _, _ = seed_transfer_in
    resp = client.get(f"/audit/set-basis/single/{trade_id}")
    html = resp.text
    assert "Split into multiple lots" in html
    assert f"/audit/set-basis/multi/{trade_id}" in html
