from datetime import date

from net_alpha.models.domain import WashSaleViolation

_YR = date.today().year


def _seed_violations(repo, items: list[dict]) -> None:
    repo.get_or_create_account("schwab", "personal")
    repo.get_or_create_account("schwab", "roth")
    vs = [
        WashSaleViolation(
            loss_trade_id=str(i),
            replacement_trade_id=str(i),
            confidence=item.get("confidence", "Confirmed"),
            disallowed_loss=item.get("disallowed_loss", 100.0),
            matched_quantity=item.get("matched_quantity", 10.0),
            ticker=item.get("ticker", "TSLA"),
            loss_account=item.get("loss_account", "schwab/personal"),
            buy_account=item.get("buy_account", "schwab/personal"),
            loss_sale_date=item.get("loss_sale_date", date(_YR, 6, 1)),
            triggering_buy_date=item.get("triggering_buy_date", date(_YR, 6, 13)),
            source=item.get("source", "engine"),
        )
        for i, item in enumerate(items)
    ]
    repo.replace_violations_in_window(date(_YR, 1, 1), date(_YR, 12, 31), vs)


def test_detail_renders_totals_bar(client, repo):
    _seed_violations(
        repo,
        [
            {"ticker": "TSLA", "disallowed_loss": 200.0, "confidence": "Confirmed"},
            {"ticker": "AAPL", "disallowed_loss": 300.0, "confidence": "Probable"},
        ],
    )
    resp = client.get("/wash-sales")
    assert resp.status_code == 200
    assert "2</span> violations" in resp.text or "2 violations" in resp.text
    assert "$500.00" in resp.text
    assert "1 confirmed" in resp.text
    assert "1 probable" in resp.text


def test_detail_groups_by_ticker_and_renders_lag(client, repo):
    _seed_violations(
        repo,
        [
            {"ticker": "TSLA", "loss_sale_date": date(_YR, 6, 1), "triggering_buy_date": date(_YR, 6, 13)},
            {"ticker": "TSLA", "loss_sale_date": date(_YR, 6, 5), "triggering_buy_date": date(_YR, 6, 20)},
            {"ticker": "AAPL", "loss_sale_date": date(_YR, 7, 1), "triggering_buy_date": date(_YR, 7, 5)},
        ],
    )
    resp = client.get("/wash-sales")
    assert resp.status_code == 200
    # Both tickers visible as group headers
    assert "TSLA" in resp.text and "AAPL" in resp.text
    # Lag values rendered
    assert "12d" in resp.text  # 6/13 - 6/1
    assert "15d" in resp.text  # 6/20 - 6/5
    assert "4d" in resp.text  # 7/5 - 7/1


def test_detail_renders_source_badges(client, repo, builders):
    # Seed a real Sell trade so the schwab_g_l violation can resolve to a TradeRow.
    builders.seed_import(
        repo,
        "schwab",
        "personal",
        [builders.make_sell("schwab/personal", "TSLA", date(_YR, 6, 1), qty=10, proceeds=1500, cost=2000)],
    )
    _seed_violations(
        repo,
        [
            {"ticker": "TSLA", "source": "schwab_g_l"},
            {"ticker": "AAPL", "source": "engine", "loss_account": "schwab/personal", "buy_account": "schwab/roth"},
            {"ticker": "MSFT", "source": "engine", "loss_account": "schwab/personal", "buy_account": "schwab/personal"},
        ],
    )
    resp = client.get("/wash-sales")
    assert resp.status_code == 200
    # All three Source badges render
    assert ">Schwab<" in resp.text
    assert ">Cross-account<" in resp.text
    assert ">Engine<" in resp.text


def test_detail_default_collapsed_when_more_than_5_tickers(client, repo):
    items = [{"ticker": f"TIC{i}", "disallowed_loss": 100.0} for i in range(6)]
    _seed_violations(repo, items)
    resp = client.get("/wash-sales")
    assert resp.status_code == 200
    # Each group's collapsible div uses x-data="{ open: false }"
    assert "open: false" in resp.text


def test_detail_default_expanded_when_5_or_fewer_tickers(client, repo):
    items = [{"ticker": f"TIC{i}", "disallowed_loss": 100.0} for i in range(3)]
    _seed_violations(repo, items)
    resp = client.get("/wash-sales")
    assert resp.status_code == 200
    assert "open: true" in resp.text


def test_detail_sort_by_lag_changes_order(client, repo):
    _seed_violations(
        repo,
        [
            {"ticker": "TSLA", "loss_sale_date": date(_YR, 6, 1), "triggering_buy_date": date(_YR, 6, 13)},  # lag 12
            {"ticker": "TSLA", "loss_sale_date": date(_YR, 7, 1), "triggering_buy_date": date(_YR, 7, 3)},  # lag 2
        ],
    )
    resp_desc = client.get("/wash-sales?sort=lag&order=desc")
    resp_asc = client.get("/wash-sales?sort=lag&order=asc")
    assert resp_desc.status_code == 200
    assert resp_asc.status_code == 200
    # Ordering check: in desc, "12d" appears before "2d"; in asc, the reverse.
    assert resp_desc.text.find("12d") < resp_desc.text.find("2d")
    assert resp_asc.text.find("2d") < resp_asc.text.find("12d")


def test_detail_filter_then_summary_reflects_filter(client, repo):
    _seed_violations(
        repo,
        [
            {"ticker": "TSLA", "disallowed_loss": 200.0, "confidence": "Confirmed"},
            {"ticker": "AAPL", "disallowed_loss": 300.0, "confidence": "Probable"},
        ],
    )
    resp = client.get("/wash-sales?ticker=TSLA")
    assert resp.status_code == 200
    assert "1</span> violations" in resp.text or "1 violations" in resp.text  # Filtered to one
    assert "$200.00" in resp.text  # Summed to one row's amount
