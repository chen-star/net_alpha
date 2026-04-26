from datetime import date


def test_imports_page_empty_state(client):
    resp = client.get("/imports")
    assert resp.status_code == 200
    assert "Imports" in resp.text
    assert "No imports yet" in resp.text


def test_imports_page_lists_imports(client, repo, builders):
    trades = [builders.make_buy("schwab/personal", "AAPL", date(2024, 5, 1), qty=10, cost=1700)]
    builders.seed_import(repo, "schwab", "personal", trades, csv_filename="aapl.csv")
    resp = client.get("/imports")
    assert resp.status_code == 200
    assert "schwab/personal" in resp.text
    assert "aapl.csv" in resp.text
