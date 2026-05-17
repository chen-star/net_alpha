"""Repository helpers for mapping a broker-exported account label to a
user-named account.

A Schwab per-account positions CSV header uses the literal broker string
("Short Term ...180"), but the user's trades live under their own label
("st"). The verify reconciler keys on (account_label, symbol), so an
unmapped CSV produces N PositionsMissingLocal + M PositionsMissingBroker
findings. Three repo helpers fix that:

* resolve_account_label(label) → canonical accounts.label (or None)
* unresolved_broker_labels(import_id) → labels in that import with no match
* set_account_broker_alias(account_id, broker_label) → set alias +
  retag all broker_position rows whose label == broker_label.

save_broker_positions also applies the resolver inline so already-mapped
labels land canonical on first write.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def seeded_accounts(repo):
    """Two real accounts mirroring the user's setup: `st` and `lt`."""
    a_st = repo.get_or_create_account("schwab", "st")
    a_lt = repo.get_or_create_account("schwab", "lt")
    return {"st": a_st, "lt": a_lt}


def _positions_rows(account_label: str, symbols: list[str]) -> list[dict]:
    return [
        {
            "account_label": account_label,
            "symbol": s,
            "qty": 1.0,
            "cost_basis": 100.0,
            "market_value": 110.0,
            "unrealized_pl": 10.0,
        }
        for s in symbols
    ]


def test_resolve_account_label_returns_none_for_unknown_label(repo, seeded_accounts):
    assert repo.resolve_account_label("Short Term ...180") is None


def test_resolve_account_label_returns_canonical_display_when_alias_set(repo, seeded_accounts):
    repo.set_account_broker_alias(account_id=seeded_accounts["st"].id, broker_label="Short Term ...180")
    assert repo.resolve_account_label("Short Term ...180") == "schwab/st"


def test_resolve_account_label_matches_existing_bare_label(repo, seeded_accounts):
    """If the broker label already equals an existing accounts.label, no
    alias needed — but the resolved form is still the display string."""
    assert repo.resolve_account_label("st") == "schwab/st"


def test_resolve_account_label_matches_existing_display_string(repo, seeded_accounts):
    """The defensive case: a CSV that already prints 'schwab/st' resolves
    straight through to itself."""
    assert repo.resolve_account_label("schwab/st") == "schwab/st"


def test_save_broker_positions_resolves_existing_alias_at_ingest(repo, seeded_accounts):
    repo.set_account_broker_alias(account_id=seeded_accounts["st"].id, broker_label="Short Term ...180")
    repo.save_broker_positions(
        rows=_positions_rows("Short Term ...180", ["AAPL", "MSFT"]),
        as_of_date="2026-05-17",
    )
    rows, _as_of = repo.latest_broker_positions()
    # All rows land in the display form so they match
    # aggregate_open_positions keys on the reconciler join.
    assert {r.account_label for r in rows} == {"schwab/st"}


def test_save_broker_positions_keeps_unresolved_label_as_is(repo, seeded_accounts):
    """Without an alias, save stores the raw broker label so the picker can find it."""
    repo.save_broker_positions(
        rows=_positions_rows("Short Term ...180", ["AAPL"]),
        as_of_date="2026-05-17",
    )
    rows, _as_of = repo.latest_broker_positions()
    assert {r.account_label for r in rows} == {"Short Term ...180"}


def test_unresolved_broker_labels_returns_labels_with_no_match(repo, seeded_accounts):
    import_id = repo.save_broker_positions(
        rows=(
            _positions_rows("Short Term ...180", ["AAPL"])
            + _positions_rows("st", ["NVDA"])  # already matches an account
            + _positions_rows("Long Term ...999", ["VOO"])
        ),
        as_of_date="2026-05-17",
    )
    unresolved = repo.unresolved_broker_labels(import_id=import_id)
    assert set(unresolved) == {"Short Term ...180", "Long Term ...999"}


def test_resolved_label_matches_aggregate_open_positions_keys(repo, seeded_accounts):
    """The whole point: after alias resolution, broker_position.account_label
    must equal the same string aggregate_open_positions() uses on the other
    side of the verify reconciler join — which is the broker/label display
    form (e.g. 'schwab/st'), not the bare nickname ('st')."""
    repo.set_account_broker_alias(account_id=seeded_accounts["st"].id, broker_label="Short Term ...180")
    repo.save_broker_positions(
        rows=_positions_rows("Short Term ...180", ["AAPL"]),
        as_of_date="2026-05-17",
    )
    bp_rows, _ = repo.latest_broker_positions()
    bp_label = bp_rows[0].account_label
    # The reconciler joins (account_label, symbol). Whatever format we
    # store must be reachable from aggregate_open_positions' key. Build
    # the expected display string from the canonical account.
    expected = f"{seeded_accounts['st'].broker}/{seeded_accounts['st'].label}"
    assert bp_label == expected


def test_set_account_broker_alias_retags_historical_broker_position_rows(repo, seeded_accounts):
    """Registering an alias rewrites already-saved broker_position rows whose
    label equals the new alias — so the user only has to map once."""
    import_id = repo.save_broker_positions(
        rows=_positions_rows("Short Term ...180", ["AAPL", "MSFT"]),
        as_of_date="2026-05-17",
    )
    # Pre-alias: rows still hold the raw broker label.
    rows, _ = repo.latest_broker_positions()
    assert {r.account_label for r in rows} == {"Short Term ...180"}

    repo.set_account_broker_alias(account_id=seeded_accounts["st"].id, broker_label="Short Term ...180")

    rows_after, _ = repo.latest_broker_positions()
    assert {r.account_label for r in rows_after} == {"schwab/st"}
    # And the just-imported import_id has no unresolved labels anymore.
    assert repo.unresolved_broker_labels(import_id=import_id) == []
