"""`/positions?view=stocks` and `/portfolio/positions?instrument_kind=stocks`
must exclude options-only rows (audit #16).

Before the fix the Stocks tab silently mirrored the All tab — ``group_options``
only affected grouping, not filtering, so an underlying with only open option
exposure (qty=0 equity, qty>0 short options) still appeared on Stocks.
"""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from net_alpha.engine.recompute import recompute_all_violations
from net_alpha.engine.stitch import stitch_account


def test_stocks_view_excludes_options_only_row(client: TestClient, builders, repo):
    """An underlying that has *only* an open short option (no equity lot) must
    appear under view=all but not under view=stocks."""
    account, _ = builders.seed_import(
        repo,
        "schwab",
        "lt",
        [
            # Plain equity holding on AAPL.
            builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5)),
            # Options-only exposure on TSLA — short put, no equity ever.
            builders.make_sto(
                "schwab/lt",
                "TSLA",
                date(2026, 2, 1),
                strike=200.0,
                expiry=date(2026, 6, 19),
                call_put="P",
            ),
        ],
    )
    stitch_account(repo, account.id)
    recompute_all_violations(repo, {})

    # All view: both tickers show up in the underlying positions table.
    res_all = client.get(
        "/portfolio/positions?period=lifetime&group_options=none&show=open"
        "&page=1&page_size=25",
        headers={"HX-Request": "true"},
    )
    assert res_all.status_code == 200
    assert "AAPL" in res_all.text
    assert "TSLA" in res_all.text

    # Stocks view: TSLA (options-only) must be filtered out.
    res_stocks = client.get(
        "/portfolio/positions?period=lifetime&group_options=none&show=open"
        "&page=1&page_size=25&instrument_kind=stocks",
        headers={"HX-Request": "true"},
    )
    assert res_stocks.status_code == 200
    assert "AAPL" in res_stocks.text
    assert "TSLA" not in res_stocks.text


def test_stocks_template_passes_instrument_kind(client: TestClient, builders, repo):
    """The stocks-view template emits an hx-get that includes
    ``instrument_kind=stocks`` so the filter actually fires."""
    builders.seed_import(
        repo,
        "schwab",
        "lt",
        [builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5))],
    )
    res = client.get("/positions?view=stocks")
    assert res.status_code == 200
    assert "instrument_kind=stocks" in res.text
