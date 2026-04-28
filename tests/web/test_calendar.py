from datetime import date, timedelta


def test_calendar_empty_state(client):
    # Calendar is now a sub-view of the wash-sales tab at /tax.
    resp = client.get("/tax?view=calendar")
    assert resp.status_code == 200
    assert "calendar" in resp.text.lower()
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
        win_start,
        win_end,
        etf_pairs={},
    )
    repo.replace_violations_in_window(win_start, win_end, result.violations)

    resp = client.get("/tax?view=calendar&year=2024")
    assert resp.status_code == 200
    assert "TSLA" in resp.text
    # The marker uses loss_sale_date in its title attribute.
    assert "2024-09-15" in resp.text


def test_calendar_focus_strip_returns_fragment(client, repo, builders):
    from datetime import timedelta

    from net_alpha.engine.detector import detect_in_window

    trades = [
        builders.make_buy("schwab/personal", "TSLA", date(2024, 8, 1), qty=10, cost=1800),
        builders.make_sell("schwab/personal", "TSLA", date(2024, 9, 15), qty=10, proceeds=1500, cost=1800),
        builders.make_buy("schwab/personal", "TSLA", date(2024, 9, 20), qty=10, cost=1600),
    ]
    builders.seed_import(repo, "schwab", "personal", trades)

    win_start = date(2024, 8, 15)
    win_end = date(2024, 10, 15)
    res = detect_in_window(
        repo.trades_in_window(win_start - timedelta(days=30), win_end + timedelta(days=30)),
        win_start,
        win_end,
        etf_pairs={},
    )
    repo.replace_violations_in_window(win_start, win_end, res.violations)
    repo.replace_lots_in_window(win_start, win_end, res.lots)

    saved = repo.all_violations()[0]
    resp = client.get(f"/wash-sales/focus/{saved.id}")
    assert resp.status_code == 200
    assert "DOCTYPE" not in resp.text  # raw fragment, not full page
    assert "TSLA" in resp.text
    assert "2024-09-15" in resp.text


def test_calendar_focus_404_for_unknown_id(client):
    resp = client.get("/wash-sales/focus/does-not-exist")
    assert resp.status_code == 404


def test_calendar_does_not_render_monthly_pl_ribbon(client, repo, builders):
    # The monthly realized-P&L ribbon was removed from the wash-sale calendar
    # — it lives on the portfolio equity curve. The page should not render
    # the "monthly realized" header.
    from datetime import date

    trades = [
        builders.make_sell("schwab/personal", "AAPL", date(2026, 3, 5), qty=10, proceeds=1500, cost=1000),
    ]
    builders.seed_import(repo, "schwab", "personal", trades)
    resp = client.get("/tax?view=calendar&year=2026")
    assert resp.status_code == 200
    assert "monthly realized" not in resp.text.lower()
