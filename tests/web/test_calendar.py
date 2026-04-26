from datetime import date, timedelta


def test_calendar_empty_state(client):
    resp = client.get("/calendar")
    assert resp.status_code == 200
    assert "Calendar" in resp.text
    assert "No wash sales" in resp.text


def test_calendar_with_violation_renders_marker(client, repo, builders):
    from net_alpha.engine.detector import detect_in_window

    trades = [
        builders.make_buy("schwab/personal", "TSLA", date(2024, 8, 1), qty=10, cost=1800),
        builders.make_sell("schwab/personal", "TSLA", date(2024, 9, 15), qty=10, proceeds=1500, cost=1800),
        builders.make_buy("schwab/personal", "TSLA", date(2024, 9, 20), qty=10, cost=1600),
    ]
    builders.seed_import(repo, "schwab", "personal", trades)

    win_start = date(2024, 8, 15)
    win_end = date(2024, 10, 15)
    result = detect_in_window(
        repo.trades_in_window(win_start - timedelta(days=30), win_end + timedelta(days=30)),
        win_start, win_end, etf_pairs={},
    )
    repo.replace_violations_in_window(win_start, win_end, result.violations)

    resp = client.get("/calendar?year=2024")
    assert resp.status_code == 200
    assert "TSLA" in resp.text
    # The marker uses loss_sale_date in its title attribute.
    assert "2024-09-15" in resp.text
