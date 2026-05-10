from datetime import date


def test_ticker_drilldown_renders_for_unknown_ticker(client):
    resp = client.get("/ticker/UNKNOWN")
    # Unknown ticker just shows empty drilldown rather than 404
    assert resp.status_code == 200
    assert "UNKNOWN" in resp.text


def test_ticker_drilldown_renders_kpis_and_sections(client, repo, builders):
    from net_alpha.engine.detector import detect_in_window

    builders.seed_import(
        repo,
        "schwab",
        "personal",
        [
            builders.make_buy("schwab/personal", "TSLA", date(2024, 8, 1), qty=10, cost=1800),
        ],
    )
    win_start, win_end = date(2024, 7, 1), date(2024, 9, 1)
    res = detect_in_window(repo.trades_in_window(win_start, win_end), win_start, win_end, etf_pairs={})
    repo.replace_lots_in_window(win_start, win_end, res.lots)

    resp = client.get("/ticker/TSLA")
    assert resp.status_code == 200
    assert "TSLA" in resp.text
    assert "Open lots" in resp.text or "open lot" in resp.text.lower()
    assert "Timeline" in resp.text or "Trade history" in resp.text


def test_jump_param_resolves_to_correct_page(client, repo, builders):
    """When ?jump=trade-{id} is given, the page returned contains the target row."""
    from net_alpha.engine.detector import detect_in_window

    # Seed 30 buys so timeline paginates at 25 rows/page.
    trades = [
        builders.make_buy("schwab/main", "AAPL", date(2024, 1, d), qty=10, cost=1000.0)
        for d in range(1, 31)
    ]
    builders.seed_import(repo, "schwab", "main", trades)
    win_start, win_end = date(2023, 12, 1), date(2024, 2, 1)
    res = detect_in_window(
        repo.trades_in_window(win_start, win_end), win_start, win_end, etf_pairs={}
    )
    repo.replace_lots_in_window(win_start, win_end, res.lots)

    saved = repo.get_trades_for_ticker("AAPL")
    target = saved[2]  # third-oldest → page 1 by default; confirm it appears on page 1

    resp = client.get(f"/ticker/AAPL?view=timeline&jump=trade-{target.id}")
    assert resp.status_code == 200
    assert f'id="trade-{target.id}"' in resp.text or target.id in resp.text


def test_jump_param_paginates_to_partner_on_other_page(client, repo, builders):
    from net_alpha.engine.detector import detect_in_window

    trades = [
        builders.make_buy("schwab/main", "AAPL", date(2024, 1, d), qty=10, cost=1000.0)
        for d in range(1, 31)
    ]
    builders.seed_import(repo, "schwab", "main", trades)
    win_start, win_end = date(2023, 12, 1), date(2024, 2, 1)
    res = detect_in_window(
        repo.trades_in_window(win_start, win_end), win_start, win_end, etf_pairs={}
    )
    repo.replace_lots_in_window(win_start, win_end, res.lots)

    saved = repo.get_trades_for_ticker("AAPL")
    page2_target = saved[27]  # past row 25 → must be on page 2

    resp = client.get(f"/ticker/AAPL?view=timeline&jump=trade-{page2_target.id}")
    assert resp.status_code == 200
    assert page2_target.id in resp.text
