"""Per-lot manual edit on the ticker page lets the user override
quantity and adjusted_basis. Writes a lot_overrides row with reason='manual'
and triggers wash-sale recompute."""

from datetime import date

from fastapi.testclient import TestClient


def test_post_lot_edit_updates_qty_and_basis(client: TestClient, builders, repo):
    builders.seed_import(repo, "schwab", "lt", [
        builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5), qty=10, cost=1500),
    ])
    from net_alpha.engine.etf_pairs import load_etf_pairs
    from net_alpha.engine.recompute import recompute_all_violations
    recompute_all_violations(repo, load_etf_pairs())

    lot = repo.get_lots_for_ticker("AAPL")[0]
    res = client.post(
        f"/lots/{lot.id}/edit",
        data={"quantity": "1.0", "adjusted_basis": "1500.0"},
    )
    assert res.status_code == 204

    # Recompute is triggered, which regenerates lots from trades + applies
    # overrides. Verify the override was recorded:
    trades = repo.get_trades_for_ticker("AAPL")
    overrides = repo.get_lot_overrides_for_trade(int(trades[0].id))
    assert any(o.field == "quantity" and o.reason == "manual" for o in overrides)


def test_post_lot_edit_returns_404_on_missing_lot(client: TestClient):
    res = client.post(
        "/lots/99999/edit",
        data={"quantity": "1.0", "adjusted_basis": "1.0"},
    )
    assert res.status_code == 404
