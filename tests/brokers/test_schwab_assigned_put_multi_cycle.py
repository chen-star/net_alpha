"""Multi-cycle assigned-put basis offsets must NOT aggregate across cycles.

Regression for the I5 bug: ``_put_assignment_basis_offsets`` summed STO
and BTC amounts across the *entire* CSV per symbol, then divided to get
a per-contract premium. A user who sells the same strike-expiry multiple
times in a year (rolling/re-selling after an assignment closes) had both
cycles' premia collapsed into a single per-contract average, so the
second cycle's assignment got contaminated by the first cycle's premia.

The fix is to bucket STO/BTC events into "assignment cycles" — each
cycle is bounded by an ``Assigned`` row for that symbol — and compute
the basis offset using only events that belong to the cycle ending at
that ``Assigned`` row.
"""

from __future__ import annotations

import pytest

from net_alpha.brokers.schwab import SchwabParser


def test_two_assignment_cycles_same_symbol_use_per_cycle_premium():
    """Cycle 1: STO at $200, immediate assignment → underlying basis $1000-$200=$800.
    Cycle 2: STO at $400, immediate assignment → underlying basis $1000-$400=$600.

    Symbol is identical (same strike+expiry). Without per-cycle bucketing
    both cycles average to $300/contract — wrong on both.
    """
    rows = [
        # Cycle 1
        {
            "Date": "01/01/2026",
            "Action": "Sell to Open",
            "Symbol": "FOO 02/20/2026 10.00 P",
            "Quantity": "1",
            "Price": "$2.00",
            "Amount": "$200.00",
        },
        {
            "Date": "02/20/2026",
            "Action": "Assigned",
            "Symbol": "FOO 02/20/2026 10.00 P",
            "Quantity": "1",
            "Price": "",
            "Amount": "",
        },
        {
            "Date": "02/20/2026",
            "Action": "Buy",
            "Symbol": "FOO",
            "Quantity": "100",
            "Price": "$10.00",
            "Amount": "-$1000.00",
        },
        # Cycle 2 (same strike-expiry symbol — user rolled after first assignment)
        {
            "Date": "03/01/2026",
            "Action": "Sell to Open",
            "Symbol": "FOO 02/20/2026 10.00 P",
            "Quantity": "1",
            "Price": "$4.00",
            "Amount": "$400.00",
        },
        {
            "Date": "04/15/2026",
            "Action": "Assigned",
            "Symbol": "FOO 02/20/2026 10.00 P",
            "Quantity": "1",
            "Price": "",
            "Amount": "",
        },
        {
            "Date": "04/15/2026",
            "Action": "Buy",
            "Symbol": "FOO",
            "Quantity": "100",
            "Price": "$10.00",
            "Amount": "-$1000.00",
        },
    ]
    trades = SchwabParser().parse(rows, account_display="schwab/personal")

    foo_buys = sorted(
        (t for t in trades if t.ticker == "FOO" and t.option_details is None),
        key=lambda t: t.date,
    )
    assert len(foo_buys) == 2
    # Cycle 1 basis: $1000 - $200 premium = $800.
    assert foo_buys[0].cost_basis == pytest.approx(800.0, abs=0.01)
    # Cycle 2 basis: $1000 - $400 premium = $600.
    # Without per-cycle bucketing this comes out as $700 (averaged with cycle 1).
    assert foo_buys[1].cost_basis == pytest.approx(600.0, abs=0.01)
