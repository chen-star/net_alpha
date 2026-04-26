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
