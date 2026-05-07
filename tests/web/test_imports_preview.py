from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def _fixture_csv() -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures" / "schwab_sample.csv"


def test_imports_preview_returns_sample_rows(client: TestClient) -> None:
    csv_path = _fixture_csv()
    with csv_path.open("rb") as f:
        resp = client.post(
            "/imports/preview",
            files=[("files", ("schwab_sample.csv", f, "text/csv"))],
        )
    assert resp.status_code == 200, resp.text
    body = resp.text
    assert "data-trade-preview" in body
    # At least one ticker from the fixture should appear in the preview
    assert any(t in body for t in ("TSLA", "AAPL", "VOO"))
