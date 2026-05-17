"""When a Schwab transactions CSV is re-imported with the option-Assigned
row missing (e.g. the user re-exported a narrower date range), the parser
re-emits the broker's raw Buy of underlying as a plain Buy at strike×qty
basis. The original import already has a synthetic ``put_assignment`` row
with premium-adjusted basis, so natural-key dedup misses (cost_basis is
part of the hash). The second-pass ``filter_assignment_duplicates`` drops
these doubles by (account, ticker, date, qty) match against existing
put_assignment trades.

Reproduces the user's RR April-20 over-count: 350 local shares vs 250
broker = 100 extra from a duplicate Apr-20 Buy at $300 (raw strike×qty),
on top of the engine-computed put_assignment Buy at $212.66 (premium-
adjusted).
"""

from __future__ import annotations

from datetime import date

from net_alpha.ingest.dedup import filter_assignment_duplicates
from net_alpha.models.domain import Trade


def _plain_buy_at_strike() -> Trade:
    """The raw Schwab Buy row from a partial re-export, parsed as basis_source='unknown'."""
    return Trade(
        account="schwab/st",
        date=date(2026, 4, 20),
        ticker="RR",
        action="Buy",
        quantity=100.0,
        proceeds=None,
        cost_basis=300.0,  # strike(3.00) × qty(100), unadjusted
        basis_source="unknown",
    )


def test_drops_plain_buy_that_duplicates_existing_put_assignment():
    trades = [_plain_buy_at_strike()]
    existing = {("schwab/st", "RR", "2026-04-20", 100.0)}
    out = filter_assignment_duplicates(trades, existing_assignments=existing)
    assert out == []


def test_keeps_plain_buy_when_no_matching_assignment():
    trades = [_plain_buy_at_strike()]
    out = filter_assignment_duplicates(trades, existing_assignments=set())
    assert len(out) == 1
    assert out[0].cost_basis == 300.0


def test_keeps_plain_buy_with_different_quantity():
    """The user has a put_assignment of 100 shares AND an unrelated market
    Buy of 50 shares on the same day. The Buy must NOT be dropped — only an
    exact (account, ticker, date, qty) match counts as a duplicate."""
    trade = Trade(
        account="schwab/st",
        date=date(2026, 4, 20),
        ticker="RR",
        action="Buy",
        quantity=50.0,
        cost_basis=200.0,
        basis_source="unknown",
    )
    existing = {("schwab/st", "RR", "2026-04-20", 100.0)}
    out = filter_assignment_duplicates([trade], existing_assignments=existing)
    assert len(out) == 1


def test_keeps_sell_trades():
    """Sells aren't subject to assignment-duplicate filtering."""
    sell = Trade(
        account="schwab/st",
        date=date(2026, 4, 20),
        ticker="RR",
        action="Sell",
        quantity=100.0,
        proceeds=500.0,
        basis_source="g_l",
    )
    existing = {("schwab/st", "RR", "2026-04-20", 100.0)}
    out = filter_assignment_duplicates([sell], existing_assignments=existing)
    assert out == [sell]


def test_keeps_option_trades():
    """Option rows (any option_details set) bypass the filter entirely."""
    from net_alpha.models.domain import OptionDetails

    opt = Trade(
        account="schwab/st",
        date=date(2026, 4, 20),
        ticker="RR",
        action="Buy",
        quantity=1.0,
        cost_basis=0.0,
        basis_source="option_short_close_assigned",
        option_details=OptionDetails(strike=3.0, expiry=date(2026, 4, 17), call_put="P"),
    )
    existing = {("schwab/st", "RR", "2026-04-20", 1.0)}
    out = filter_assignment_duplicates([opt], existing_assignments=existing)
    assert out == [opt]


def test_keeps_buys_with_explicit_basis_source():
    """A Buy whose parser already classified it (g_l, transfer_in, etc.) is
    NOT a candidate for assignment-dup filtering — only basis_source='unknown'
    (the parser's fallback) is."""
    trade = Trade(
        account="schwab/st",
        date=date(2026, 4, 20),
        ticker="RR",
        action="Buy",
        quantity=100.0,
        cost_basis=300.0,
        basis_source="transfer_in",
    )
    existing = {("schwab/st", "RR", "2026-04-20", 100.0)}
    out = filter_assignment_duplicates([trade], existing_assignments=existing)
    assert out == [trade]


