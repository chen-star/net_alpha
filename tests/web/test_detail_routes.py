from datetime import date

from net_alpha.models.domain import WashSaleViolation


def test_detail_empty_state(client, repo, builders):
    # Seed a no-violation import so the page-level empty hero doesn't suppress
    # the tab body — we're asserting the in-tab affirmative copy.
    builders.seed_import(
        repo,
        "schwab",
        "personal",
        [builders.make_buy("schwab/personal", "AAPL", date(2024, 5, 1))],
    )
    resp = client.get("/wash-sales")
    assert resp.status_code == 200
    assert "Wash sales" in resp.text
    assert "no wash-sale violations detected" in resp.text.lower() or "✓" in resp.text


def test_detail_filter_by_ticker(client, repo, builders):
    # Seed an account first so violation account display strings can resolve.
    repo.get_or_create_account("schwab", "personal")
    v = WashSaleViolation(
        loss_trade_id="0",
        replacement_trade_id="0",
        confidence="Confirmed",
        disallowed_loss=300.0,
        matched_quantity=10.0,
        ticker="TSLA",
        loss_account="schwab/personal",
        buy_account="schwab/personal",
        loss_sale_date=date(2024, 9, 15),
        triggering_buy_date=date(2024, 9, 20),
    )
    repo.replace_violations_in_window(date(2024, 8, 15), date(2024, 10, 15), [v])

    resp = client.get("/wash-sales?ticker=TSLA")
    assert resp.status_code == 200
    assert "TSLA" in resp.text
    assert "schwab/personal" in resp.text
