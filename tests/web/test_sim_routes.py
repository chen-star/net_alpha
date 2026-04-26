from datetime import date


def test_sim_form_renders(client):
    resp = client.get("/sim")
    assert resp.status_code == 200
    assert "Simulate" in resp.text or "Sim" in resp.text


def test_sim_post_with_no_holdings_returns_message(client):
    resp = client.post("/sim", data={"ticker": "AAPL", "qty": "10", "price": "180"})
    assert resp.status_code == 200
    assert "No holdings" in resp.text or "no open lots" in resp.text.lower()


def test_sim_post_with_held_ticker_returns_per_account_card(client, repo, builders):
    from net_alpha.engine.detector import detect_in_window
    builders.seed_import(repo, "schwab", "personal", [
        builders.make_buy("schwab/personal", "TSLA", date(2024, 6, 1), qty=10, cost=1800),
    ])
    win_start, win_end = date(2024, 5, 1), date(2024, 7, 1)
    res = detect_in_window(repo.trades_in_window(win_start, win_end),
                           win_start, win_end, etf_pairs={})
    repo.replace_lots_in_window(win_start, win_end, res.lots)

    resp = client.post("/sim", data={"ticker": "TSLA", "qty": "5", "price": "150"})
    assert resp.status_code == 200
    assert "schwab/personal" in resp.text
