from datetime import date


def test_import_detail_returns_fragment(client, repo, builders):
    trades = [
        builders.make_buy("schwab/personal", "AAPL", date(2026, 1, 5), qty=10, cost=1500),
        builders.make_buy("schwab/personal", "MSFT", date(2026, 1, 10), qty=5, cost=2000),
    ]
    _, import_id = builders.seed_import(repo, "schwab", "personal", trades, csv_filename="trades.csv")

    resp = client.get(f"/imports/{import_id}/detail")
    assert resp.status_code == 200
    assert "DOCTYPE" not in resp.text
    body = resp.text
    assert "schwab" in body.lower()
    assert "personal" in body
    assert "AAPL" in body
    assert "MSFT" in body
    # Distinct ticker count surfaced.
    assert "2" in body


def test_import_detail_404_for_unknown_id(client):
    resp = client.get("/imports/999999/detail")
    assert resp.status_code == 404
