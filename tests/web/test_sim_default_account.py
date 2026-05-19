"""When there is exactly one account, /sim must preselect it.

Regression: the Account select defaulted to ``All`` (value="") which is
flagged "required" for Sell action. Users hit the form, picked Sell,
clicked Run sim, then got an error — the friction was visible in the UX
audit. With one account the answer is unambiguous; preselect it.

With 2+ accounts, the default stays empty so the user must consciously
choose (we don't want a silent default selecting the wrong account on a
multi-account portfolio).
"""

from __future__ import annotations

from datetime import date

from tests.web.conftest import make_buy, seed_import


def test_sim_form_preselects_sole_account(client, repo):
    """A repo with exactly one account preselects it in the Account dropdown."""
    seed_import(
        repo,
        "schwab",
        "personal",
        [make_buy("schwab/personal", "SPY", date(2024, 1, 15), qty=10, cost=800)],
    )

    r = client.get("/sim")
    assert r.status_code == 200
    body = r.text
    # The dropdown markup is `<option value="schwab/personal" selected>schwab/personal</option>`.
    assert 'value="schwab/personal" selected' in body


def test_sim_form_two_accounts_does_not_preselect(client, repo):
    """Multiple accounts → user must choose; no silent default."""
    seed_import(
        repo,
        "schwab",
        "lt",
        [make_buy("schwab/lt", "SPY", date(2024, 1, 15), qty=10, cost=800)],
    )
    seed_import(
        repo,
        "schwab",
        "st",
        [make_buy("schwab/st", "QQQ", date(2024, 6, 15), qty=5, cost=2000)],
    )

    r = client.get("/sim")
    body = r.text
    # Neither account marker is preselected — only the All option carries
    # the (default) selected state, and that's enforced by it being the
    # first option with value="".
    assert 'value="schwab/lt" selected' not in body
    assert 'value="schwab/st" selected' not in body


def test_sim_form_explicit_account_param_overrides_preselect(client, repo):
    """When ?account=… is in the URL, that wins regardless of account count."""
    seed_import(
        repo,
        "schwab",
        "lt",
        [make_buy("schwab/lt", "SPY", date(2024, 1, 15), qty=10, cost=800)],
    )
    seed_import(
        repo,
        "schwab",
        "st",
        [make_buy("schwab/st", "QQQ", date(2024, 6, 15), qty=5, cost=2000)],
    )
    r = client.get("/sim?account=schwab%2Fst")
    body = r.text
    assert 'value="schwab/st" selected' in body
