"""Caveats surface when a multi-account filter is active."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_carryforward_caveat_absent_when_no_filter(client: TestClient):
    resp = client.get("/tax?view=performance")
    assert resp.status_code == 200
    assert "Carryforward applied is taxpayer-level" not in resp.text


def test_carryforward_caveat_present_when_filter_active(client: TestClient):
    resp = client.get("/tax?view=performance&account=Schwab%2FTax")
    assert resp.status_code == 200
    assert "Carryforward applied is taxpayer-level" in resp.text


def test_harvest_offset_budget_caveat_absent_when_no_filter(client: TestClient):
    resp = client.get("/tax/harvest/plan")
    assert resp.status_code == 200
    assert "Offset budget is taxpayer-level" not in resp.text


def test_harvest_offset_budget_caveat_present_when_filter_active(client: TestClient):
    resp = client.get("/tax/harvest/plan?account=Schwab%2FTax")
    assert resp.status_code == 200
    assert "Offset budget is taxpayer-level" in resp.text
