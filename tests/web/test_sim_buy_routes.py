from datetime import date


def test_sim_form_includes_action_toggle_and_date(client):
    resp = client.get("/sim")
    assert resp.status_code == 200
    assert "Buy" in resp.text and "Sell" in resp.text
    assert 'name="trade_date"' in resp.text
    assert 'name="action"' in resp.text


def test_sim_post_buy_with_no_recent_losses_returns_clean_options(client, repo):
    repo.get_or_create_account("schwab", "personal")
    resp = client.post(
        "/sim",
        data={
            "action": "buy",
            "ticker": "TSLA",
            "qty": "10",
            "price": "180",
            "account": "schwab/personal",
            "trade_date": "2025-06-01",
        },
    )
    assert resp.status_code == 200
    # Buy partial heading
    assert "options for buying" in resp.text
    # Clean state
    assert "No wash sale" in resp.text


def test_sim_post_buy_with_recent_loss_shows_wash_trigger(client, repo, builders):
    from net_alpha.engine.detector import detect_in_window

    builders.seed_import(
        repo,
        "schwab",
        "personal",
        [
            builders.make_buy("schwab/personal", "TSLA", date(2025, 4, 1), qty=10, cost=2000),
            builders.make_sell("schwab/personal", "TSLA", date(2025, 5, 20), qty=10, proceeds=1500, cost=2000),
        ],
    )
    # Run detector so that any pre-existing buy doesn't accidentally already wash-match.
    win_start, win_end = date(2025, 4, 1), date(2025, 7, 1)
    res = detect_in_window(repo.trades_in_window(win_start, win_end), win_start, win_end, etf_pairs={})
    repo.replace_lots_in_window(win_start, win_end, res.lots)
    repo.replace_violations_in_window(win_start, win_end, res.violations)

    resp = client.post(
        "/sim",
        data={
            "action": "buy",
            "ticker": "TSLA",
            "qty": "10",
            "price": "180",
            "account": "schwab/personal",
            "trade_date": "2025-06-01",
        },
    )
    assert resp.status_code == 200
    assert "Wash trigger" in resp.text
    assert "Disallowed loss rolled in" in resp.text


def test_sim_post_sell_still_works(client, repo, builders):
    from net_alpha.engine.detector import detect_in_window

    builders.seed_import(
        repo,
        "schwab",
        "personal",
        [
            builders.make_buy("schwab/personal", "TSLA", date(2025, 4, 1), qty=10, cost=2000),
        ],
    )
    win_start, win_end = date(2025, 3, 1), date(2025, 7, 1)
    res = detect_in_window(repo.trades_in_window(win_start, win_end), win_start, win_end, etf_pairs={})
    repo.replace_lots_in_window(win_start, win_end, res.lots)

    resp = client.post(
        "/sim",
        data={
            "action": "sell",
            "ticker": "TSLA",
            "qty": "5",
            "price": "150",
            "account": "schwab/personal",
            "trade_date": "2025-06-01",
        },
    )
    assert resp.status_code == 200
    assert "schwab/personal" in resp.text
    # Sell partial heading uses "options for"
    assert "options for" in resp.text
