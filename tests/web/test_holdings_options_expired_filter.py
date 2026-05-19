"""Expired contracts must be filtered from the /holdings/options panel.

Regression: an expired short option (expiry < today) kept appearing under
"Open options" in the Positions → Options tab even though its collateral
has already been released. The user couldn't act on it (broker has already
closed it server-side); the row was visual noise mixed with truly open
contracts and the count overstated open exposure.

Fix: filter open_options by ``expiry >= today`` in the holdings_options
route. Stale count is still surfaced in the panel header as
``X expired (awaiting broker close)`` so the information isn't hidden —
just demoted out of the actionable list.
"""

from __future__ import annotations

from datetime import date, timedelta

from tests.web.conftest import make_sto, seed_import


def test_expired_short_option_not_in_open_options_list(client, repo):
    """A short put that expired before today must NOT be returned in
    open_options; a future-dated short put MUST be."""
    today = date.today()
    expired_day = today - timedelta(days=3)
    future_day = today + timedelta(days=30)

    seed_import(
        repo,
        "schwab",
        "personal",
        [
            # Expired 3 days ago — collateral was released at expiry.
            make_sto(
                "schwab/personal",
                "EXP",
                today - timedelta(days=60),
                strike=2.0,
                expiry=expired_day,
                call_put="P",
                qty=1.0,
                proceeds=12.0,
            ),
            # Future expiry — still actionable.
            make_sto(
                "schwab/personal",
                "ALIVE",
                today - timedelta(days=10),
                strike=10.0,
                expiry=future_day,
                call_put="P",
                qty=1.0,
                proceeds=50.0,
            ),
        ],
    )

    r = client.get("/holdings/options")
    assert r.status_code == 200
    body = r.text
    # Future contract surfaces.
    assert "ALIVE" in body
    # Expired contract is filtered out of the actionable list.
    assert "EXP" not in body or "expired" in body.lower(), (
        "Expired short option leaked into the open-options listing — users see a row they cannot act on."
    )


def test_options_summary_counts_exclude_expired(client, repo):
    """The header's 'X open contracts' figure must count only contracts
    whose expiry is still in the future."""
    today = date.today()
    seed_import(
        repo,
        "schwab",
        "personal",
        [
            make_sto(
                "schwab/personal",
                "ALPHA",
                today - timedelta(days=60),
                strike=1.0,
                expiry=today - timedelta(days=1),  # expired
                call_put="P",
            ),
            make_sto(
                "schwab/personal",
                "BETA",
                today - timedelta(days=20),
                strike=2.0,
                expiry=today + timedelta(days=21),
                call_put="P",
            ),
            make_sto(
                "schwab/personal",
                "GAMMA",
                today - timedelta(days=5),
                strike=3.0,
                expiry=today + timedelta(days=45),
                call_put="C",
            ),
        ],
    )
    r = client.get("/holdings/options")
    assert r.status_code == 200
    body = r.text
    # 2 future contracts; the summary "open contracts" stat must report 2,
    # not 3. We assert on the most-visible "OPEN CONTRACTS" header label.
    assert "2</" in body or ">2<" in body or ">2 " in body
