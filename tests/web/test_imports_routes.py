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


def test_delete_import_removes_it_and_returns_table_fragment(client, repo, builders):
    _, import_id = builders.seed_import(
        repo,
        "schwab",
        "personal",
        [builders.make_buy("schwab/personal", "AAPL", date(2024, 5, 1))],
        csv_filename="aapl.csv",
    )
    assert len(repo.list_imports()) == 1

    resp = client.delete(f"/imports/{import_id}")
    assert resp.status_code == 200
    assert "No imports yet" in resp.text  # fragment shows empty state
    assert "DOCTYPE" not in resp.text  # raw fragment, not full page
    assert len(repo.list_imports()) == 0


def test_delete_nonexistent_import_returns_404(client):
    resp = client.delete("/imports/999")
    assert resp.status_code == 404
