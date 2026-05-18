"""Put-assignment dedup must NOT drop a new Buy when the existing key has
multiple matching put_assignments at different strikes.

Regression for the I7 bug: the dedup key is
``(account, ticker, date, qty)`` — strike is not part of the key. When
two different-strike puts on the same ticker get assigned on the same
day at the same contract count, both existing put_assignment rows share
this key. A partial re-import bringing one (genuinely new) underlying
Buy at a third strike matches the existing key and gets silently
dropped — the user loses that lot's basis.

Safe-by-default fix: when ``existing_assignments`` indicates 2+ rows
share a key, leave new Buys with that key alone so the user keeps the
data and can manually resolve any duplicates from the Imports page.
"""

from __future__ import annotations

from datetime import date

from net_alpha.ingest.dedup import filter_assignment_duplicates
from net_alpha.models.domain import Trade


def _plain_buy(amount: float) -> Trade:
    return Trade(
        account="schwab/personal",
        date=date(2026, 4, 17),
        ticker="X",
        action="Buy",
        quantity=100.0,
        proceeds=None,
        cost_basis=amount,
        basis_source="unknown",
    )


def test_drops_when_one_existing_match():
    """Baseline: single existing put_assignment for the key → drop the dupe."""
    out = filter_assignment_duplicates(
        [_plain_buy(500.0)],
        existing_assignments={("schwab/personal", "X", "2026-04-17", 100.0): 1},
    )
    assert out == []


def test_keeps_new_buy_when_existing_key_has_two_assignments():
    """Two existing put_assignments share the key — we can't tell which the
    new Buy duplicates (or whether it's a third strike entirely), so leave
    it in. Better to keep a duplicate that the user can delete than to lose
    a genuine new lot's basis silently."""
    out = filter_assignment_duplicates(
        [_plain_buy(700.0)],
        existing_assignments={("schwab/personal", "X", "2026-04-17", 100.0): 2},
    )
    assert len(out) == 1
    assert out[0].cost_basis == 700.0


def test_keeps_legacy_set_callers_working():
    """``existing_assignments`` historically was a ``set`` of keys (count=1).
    Calling with a set must keep the legacy semantics."""
    out = filter_assignment_duplicates(
        [_plain_buy(500.0)],
        existing_assignments={("schwab/personal", "X", "2026-04-17", 100.0)},
    )
    assert out == []
