"""Test that violation source badges render correctly in HTML output."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from net_alpha.models.domain import ImportRecord, Trade, WashSaleViolation


def _seed_violation(repo, source: str, confidence: str = "Confirmed") -> None:
    """Insert a fixture trade pair + a violation with a specific source."""
    acct = repo.get_or_create_account("schwab", "personal")
    rec = ImportRecord(
        account_id=acct.id,
        csv_filename="t.csv",
        csv_sha256="abc",
        imported_at=datetime(2026, 4, 25),
        trade_count=2,
    )
    trades = [
        Trade(
            account=acct.display(),
            date=date(2026, 4, 1),
            ticker="WRD",
            action="Buy",
            quantity=100,
            cost_basis=900.0,
        ),
        Trade(
            account=acct.display(),
            date=date(2026, 4, 20),
            ticker="WRD",
            action="Sell",
            quantity=100,
            proceeds=800.0,
            cost_basis=900.0,
        ),
    ]
    repo.add_import(acct, rec, trades)
    all_trades = repo.all_trades()
    sell = next(t for t in all_trades if t.action == "Sell")
    buy = next(t for t in all_trades if t.action == "Buy")
    v = WashSaleViolation(
        loss_trade_id=sell.id,
        replacement_trade_id=buy.id,
        confidence=confidence,
        disallowed_loss=100.0,
        matched_quantity=100,
        loss_account=acct.display(),
        buy_account=acct.display(),
        loss_sale_date=date(2026, 4, 20),
        triggering_buy_date=date(2026, 4, 1),
        ticker="WRD",
        source=source,
    )
    win_start = date(2026, 4, 1) - timedelta(days=30)
    win_end = date(2026, 4, 20) + timedelta(days=30)
    repo.replace_violations_in_window(win_start, win_end, [v])


def test_calendar_focus_renders_schwab_source_badge(client, repo):
    _seed_violation(repo, source="schwab_g_l")
    violations = repo.all_violations()
    assert len(violations) == 1
    vid = violations[0].id
    resp = client.get(f"/wash-sales/focus/{vid}")
    assert resp.status_code == 200
    assert "schwab" in resp.text.lower()


def test_calendar_focus_renders_engine_source_badge(client, repo):
    _seed_violation(repo, source="engine", confidence="Probable")
    violations = repo.all_violations()
    vid = violations[0].id
    resp = client.get(f"/wash-sales/focus/{vid}")
    assert resp.status_code == 200
    assert "engine" in resp.text.lower() or "cross-account" in resp.text.lower()
