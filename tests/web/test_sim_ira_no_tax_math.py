"""Sim sells inside a tax-advantaged account must not show tax math.

Losses realized inside an IRA / Roth / 401(k) / HSA are not deductible and
gains aren't taxed, so the after-tax lot-strategy comparison and the
"Lot method recommended" headline are meaningless — and actively misleading,
since they imply a tax benefit (smaller after-tax loss) that does not exist.
The Sim must suppress that tax math for tax-advantaged accounts and explain why.
"""

from __future__ import annotations

from datetime import date

import pytest


@pytest.fixture
def ira_sim_setup(client, repo, builders):
    """Seed 100 SPY shares in a trad-IRA account, materialize the lot."""
    from net_alpha.engine.detector import detect_in_window

    builders.seed_import(
        repo,
        "schwab",
        "ira",
        [builders.make_buy("schwab/ira", "SPY", date(2024, 1, 15), qty=100, cost=8000)],
    )
    repo.set_account_type(broker="schwab", label="ira", type_="trad_ira")
    win_start, win_end = date(2023, 12, 1), date(2024, 3, 1)
    res = detect_in_window(
        repo.trades_in_window(win_start, win_end),
        win_start,
        win_end,
        etf_pairs={},
    )
    repo.replace_lots_in_window(win_start, win_end, res.lots)
    return client, repo


def test_ira_sell_suppresses_after_tax_comparison(ira_sim_setup):
    client, _ = ira_sim_setup
    resp = client.post(
        "/sim",
        data={
            "ticker": "SPY",
            "qty": "50",
            "price": "40",  # sell well below $80/sh basis → a loss
            "action": "sell",
            "account": "schwab/ira",
        },
    )
    assert resp.status_code == 200
    body = resp.text
    # No tax-optimization table for a tax-advantaged account: the comparison
    # <section id="sim-lot-comparison"> and its After-tax column are absent.
    assert 'id="sim-lot-comparison"' not in body
    assert "After-tax" not in body
    # Explanatory note shown instead.
    assert "tax-advantaged" in body.lower()


def test_ira_sell_omits_lot_method_headline(ira_sim_setup):
    client, _ = ira_sim_setup
    resp = client.post(
        "/sim",
        data={
            "ticker": "SPY",
            "qty": "50",
            "price": "40",
            "action": "sell",
            "account": "schwab/ira",
        },
    )
    assert resp.status_code == 200
    # The "Lot method recommended: HIFO" headline is a tax-optimization hint.
    assert "Lot method recommended" not in resp.text


def test_taxable_sell_still_shows_comparison(ira_sim_setup):
    """Guard: the suppression is scoped to tax-advantaged accounts only — a
    taxable account still gets the full comparison."""
    client, repo = ira_sim_setup
    from datetime import date as _date

    from net_alpha.engine.detector import detect_in_window

    repo.get_or_create_account("schwab", "brokerage")
    # Reuse the builder seed for a taxable account.
    from tests.web.conftest import make_buy, seed_import

    buy = make_buy("schwab/brokerage", "QQQ", _date(2024, 1, 15), qty=100, cost=8000)
    seed_import(repo, "schwab", "brokerage", [buy])
    res = detect_in_window(
        repo.trades_in_window(_date(2023, 12, 1), _date(2024, 3, 1)),
        _date(2023, 12, 1),
        _date(2024, 3, 1),
        etf_pairs={},
    )
    repo.replace_lots_in_window(_date(2023, 12, 1), _date(2024, 3, 1), res.lots)

    resp = client.post(
        "/sim",
        data={
            "ticker": "QQQ",
            "qty": "50",
            "price": "40",
            "action": "sell",
            "account": "schwab/brokerage",
        },
    )
    assert resp.status_code == 200
    assert "Lot strategy comparison" in resp.text
