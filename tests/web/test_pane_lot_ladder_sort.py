"""Lot ladder column-header sort (client-side Alpine).

Pure structural tests: confirm the headers render with sort hooks and the
rows expose machine-sortable data attributes. The actual Alpine click
behavior can't be exercised from the FastAPI TestClient (would need
Playwright); the sort column appears in the template and the data attrs
are correct.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient


def test_ladder_renders_column_headers(client: TestClient, repo, builders) -> None:
    from net_alpha.engine.recompute import recompute_all_violations
    from net_alpha.engine.stitch import stitch_account

    sym = "SORTCOLS"
    today = date.today()
    display = "Schwab/Taxable"
    buy = builders.make_buy(display, sym, today - timedelta(days=30), qty=10.0, cost=1000.0)
    acct, _ = builders.seed_import(repo, "Schwab", "Taxable", [buy])
    stitch_account(repo, acct.id)
    recompute_all_violations(repo, {})
    resp = client.get(f"/positions/pane?sym={sym}&account_id={acct.id}")
    assert resp.status_code == 200
    html = resp.text
    assert 'data-testid="lot-ladder-header"' in html
    for col in ("date", "qty", "basis", "unrealized", "status"):
        assert f'data-sort-col="{col}"' in html


def test_lot_rows_carry_sortable_data_attrs(client: TestClient, repo, builders) -> None:
    from net_alpha.engine.recompute import recompute_all_violations
    from net_alpha.engine.stitch import stitch_account

    sym = "SORTDATA"
    today = date.today()
    display = "Schwab/Taxable"
    buy = builders.make_buy(display, sym, today - timedelta(days=30), qty=10.0, cost=1000.0)
    acct, _ = builders.seed_import(repo, "Schwab", "Taxable", [buy])
    stitch_account(repo, acct.id)
    recompute_all_violations(repo, {})
    resp = client.get(f"/positions/pane?sym={sym}&account_id={acct.id}")
    assert resp.status_code == 200
    html = resp.text
    # Each row must expose attrs the Alpine sort handler reads:
    assert "data-row-date=" in html
    assert "data-row-qty=" in html
    assert "data-row-basis=" in html
    # unrealized may or may not be present depending on price availability;
    # if it's there, must be a numeric attribute.
    # data-pill is already there from earlier tasks.


def test_alpine_sort_handler_present_in_template() -> None:
    """Sanity check the template still wires the Alpine sort handler."""
    tpl = Path(__file__).parents[2] / "src/net_alpha/web/templates/_positions_pane_lot_ladder.html"
    text = tpl.read_text()
    assert "sortBy" in text
    assert "applySort" in text
    assert "sortCol" in text and "sortDesc" in text


def test_lot_ladder_header_omitted_for_empty_lot_list(client: TestClient) -> None:
    """No lots → no ladder, no header (the existing ``{% if lot_rows %}`` guard
    covers this)."""
    resp = client.get("/positions/pane?sym=NONEXIST")
    assert resp.status_code == 200
    assert 'data-testid="lot-ladder-header"' not in resp.text
