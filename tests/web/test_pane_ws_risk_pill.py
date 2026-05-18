"""WS risk pill in the lot ladder.

A lot is WS-implicated if its cost basis was inflated by a §1091(d)
disallowed-loss roll-in (i.e., its trade_id matches the replacement_trade_id
on at least one WashSaleViolation). The ladder surfaces this as:
  - data-pill="WS" on the row's status pill
  - A title tooltip citing IRC §1091(d)

Status precedence: TACKED > WS > LT > ST. When a lot is both TACKED (holding-
period tacked per §1223(4)) and WS-implicated (basis inflated per §1091(d)) —
the common wash-sale outcome — TACKED wins for the pill. The WS pill appears
only for WS-implicated lots that were NOT tacked.

In practice the engine rolls basis AND tacks holding period together for every
deferred wash sale, so the TACKED path is the dominant code path tested here.
The WS-only (non-tacked) scenario is structural — covered by the template
string check.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# 1. Combined TACKED+WS scenario (standard wash-sale outcome)
#    TACKED wins the pill; route must still populate ws_implicated_trade_ids.
# ---------------------------------------------------------------------------


def test_tacked_wins_over_ws_when_both_apply(client: TestClient, repo, builders) -> None:
    """Standard wash-sale: buy → sell at loss → rebuy.

    Engine assigns both tacked_acquired_date AND inflates adjusted_basis on
    the replacement lot. Per the precedence rule, the pill must show TACKED
    (not WS), because the holding-period concern is more material.
    """
    from net_alpha.engine.recompute import recompute_all_violations
    from net_alpha.engine.stitch import stitch_account

    sym = "WSPILL"
    today = date.today()
    display = "Schwab/Taxable"

    buy_old = builders.make_buy(display, sym, today - timedelta(days=730), qty=100.0, cost=10_000.0)
    sell_old = builders.make_sell(display, sym, today - timedelta(days=30), qty=100.0, cost=10_000.0, proceeds=5_000.0)
    rebuy = builders.make_buy(display, sym, today - timedelta(days=10), qty=100.0, cost=5_000.0)

    acct, _ = builders.seed_import(repo, "Schwab", "Taxable", [buy_old, sell_old, rebuy])
    stitch_account(repo, acct.id)
    recompute_all_violations(repo, {})

    # Sanity-check: engine must have produced a violation + a tacked lot.
    violations = repo.get_violations_for_ticker(sym)
    assert len(violations) >= 1, "engine should detect at least one wash sale"
    lots = repo.get_lots_for_ticker(sym)
    tacked = [lot for lot in lots if lot.account == display and lot.tacked_acquired_date is not None]
    assert len(tacked) == 1, f"expected 1 tacked lot, got {len(tacked)}"

    resp = client.get(f"/positions/pane?sym={sym}&account_id={acct.id}")
    assert resp.status_code == 200
    html = resp.text

    # TACKED must win for the pill.
    assert 'data-pill="TACKED"' in html, "TACKED pill must render for tacked+WS lot"
    # WS pill should NOT appear when TACKED wins.
    assert 'data-pill="WS"' not in html, "WS pill must not appear when TACKED takes precedence"
    # The §1223(4) tooltip must be present.
    assert "1223(4)" in html, "§1223(4) tooltip must appear on the TACKED lot row"


# ---------------------------------------------------------------------------
# 2. Unit: _pane_lot_info produces WS status for a non-tacked WS-implicated lot
# ---------------------------------------------------------------------------


def test_pane_lot_info_ws_status_without_tack() -> None:
    """When a lot is WS-implicated but not tacked, _pane_lot_info must set
    status='WS' and is_ws_implicated=True."""
    import datetime as dt

    from net_alpha.models.domain import Lot
    from net_alpha.web.routes.positions import _pane_lot_info

    trade_id = "trade-abc-123"
    lot = Lot(
        trade_id=trade_id,
        account="Schwab/Taxable",
        date=dt.date(2025, 3, 1),
        ticker="WSTST",
        quantity=50.0,
        cost_basis=5_000.0,
        adjusted_basis=7_500.0,  # inflated by $2,500 disallowed loss roll-in
        tacked_acquired_date=None,  # NOT tacked — the WS-only scenario
    )
    today = dt.date(2025, 6, 1)  # ~91 days held → short-term

    result = _pane_lot_info(
        open_equity_lots=[lot],
        last_price=None,
        today=today,
        ws_implicated_trade_ids={trade_id},
    )
    row = result["lots"][0]
    assert row["status"] == "WS", f"expected 'WS', got {row['status']!r}"
    assert row["is_ws_implicated"] is True


def test_pane_lot_info_no_ws_when_trade_id_absent() -> None:
    """A lot whose trade_id is NOT in ws_implicated_trade_ids gets standard ST/LT."""
    import datetime as dt

    from net_alpha.models.domain import Lot
    from net_alpha.web.routes.positions import _pane_lot_info

    lot = Lot(
        trade_id="trade-xyz",
        account="Schwab/Taxable",
        date=dt.date(2025, 3, 1),
        ticker="WSTST2",
        quantity=50.0,
        cost_basis=5_000.0,
        adjusted_basis=5_000.0,
        tacked_acquired_date=None,
    )
    today = dt.date(2025, 6, 1)

    result = _pane_lot_info(
        open_equity_lots=[lot],
        last_price=None,
        today=today,
        ws_implicated_trade_ids={"some-other-trade-id"},
    )
    row = result["lots"][0]
    assert row["status"] == "ST"
    assert row["is_ws_implicated"] is False


def test_pane_lot_info_tacked_wins_over_ws() -> None:
    """When a lot has both tacked_acquired_date and is WS-implicated, status='TACKED'."""
    import datetime as dt

    from net_alpha.models.domain import Lot
    from net_alpha.web.routes.positions import _pane_lot_info

    trade_id = "trade-tacked-ws"
    lot = Lot(
        trade_id=trade_id,
        account="Schwab/Taxable",
        date=dt.date(2025, 3, 1),
        ticker="WSCK",
        quantity=100.0,
        cost_basis=5_000.0,
        adjusted_basis=10_000.0,
        tacked_acquired_date=dt.date(2023, 1, 1),  # tacked far back → LT effective
    )
    today = dt.date(2025, 6, 1)

    result = _pane_lot_info(
        open_equity_lots=[lot],
        last_price=None,
        today=today,
        ws_implicated_trade_ids={trade_id},
    )
    row = result["lots"][0]
    assert row["status"] == "TACKED", f"TACKED must win over WS, got {row['status']!r}"
    assert row["is_ws_implicated"] is True, "is_ws_implicated must still be True even when TACKED wins"
    assert row["is_tacked"] is True


# ---------------------------------------------------------------------------
# 3. Template carries the required §1091(d) string and WS branch
# ---------------------------------------------------------------------------


def test_template_contains_1091d_tooltip() -> None:
    """The lot ladder template must include the §1091(d) tooltip text for the
    non-tacked WS-implicated scenario, even if the scenario is rarely hit
    in production data."""
    from pathlib import Path

    tpl = Path(__file__).parents[2] / "src/net_alpha/web/templates/_positions_pane_lot_ladder.html"
    text = tpl.read_text()
    assert "1091(d)" in text, "WS tooltip must cite IRC §1091(d)"
    assert "'WS'" in text or '"WS"' in text, "Template must have a WS branch (pill label or CSS branch)"
