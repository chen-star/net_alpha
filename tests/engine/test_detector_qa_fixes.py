"""QA-audit regression tests for wash-sale detector bugs.

Covers:
  * H5 — STO-put as wash-sale replacement candidate recorded
         `kind="deferred"` but silently never rolled basis (no equity lot
         exists for an STO). The loss was effectively lost without any
         signal to the user. Now classified `kind="deferred_to_contract"`,
         which surfaces the situation correctly.
"""

from __future__ import annotations

from datetime import date

from net_alpha.engine.detector import detect_wash_sales
from net_alpha.models.domain import OptionDetails, Trade


def test_sold_put_replacement_uses_deferred_to_contract_kind():
    """A loss sale followed by a sold put within 30 days must record a
    violation flagged as `deferred_to_contract` — signalling that the
    disallowed loss can't be rolled onto an equity lot in our schema
    and requires manual tracking against the option contract.
    """
    # Loss sale on AAPL (taxable).
    loss = Trade(
        id="L1",
        account="schwab/tax",
        date=date(2026, 3, 1),
        ticker="AAPL",
        action="Sell",
        quantity=10,
        proceeds=1000.0,
        cost_basis=1500.0,
    )
    # Sold put on AAPL within the wash-sale window — a "contract to acquire"
    # under §1091. No buy lot is created for an STO.
    sold_put = Trade(
        id="P1",
        account="schwab/tax",
        date=date(2026, 3, 15),
        ticker="AAPL",
        action="Sell",
        quantity=1,
        proceeds=200.0,
        cost_basis=0.0,
        option_details=OptionDetails(strike=145.0, expiry=date(2026, 6, 19), call_put="P"),
        basis_source="option_short_open",
    )

    result = detect_wash_sales([loss, sold_put], etf_pairs={})
    assert len(result.violations) == 1
    v = result.violations[0]
    assert v.kind == "deferred_to_contract"
    assert v.disallowed_loss > 0
    # No equity lot should be mutated since the STO has no lot.
    aapl_lots = [lot for lot in result.lots if lot.ticker == "AAPL"]
    for lot in aapl_lots:
        # Loss sale's underlying lots should remain at their original basis
        # (no mutation against the sold-put "replacement").
        assert lot.tacked_acquired_date is None


def test_equity_replacement_still_uses_deferred_kind():
    """Sanity check: an equity-to-equity wash sale is unaffected by the new
    `deferred_to_contract` branch.
    """
    loss = Trade(
        id="L1",
        account="schwab/tax",
        date=date(2026, 3, 1),
        ticker="AAPL",
        action="Sell",
        quantity=10,
        proceeds=1000.0,
        cost_basis=1500.0,
    )
    replacement = Trade(
        id="B1",
        account="schwab/tax",
        date=date(2026, 3, 10),
        ticker="AAPL",
        action="Buy",
        quantity=10,
        cost_basis=1100.0,
    )
    result = detect_wash_sales([loss, replacement], etf_pairs={})
    assert len(result.violations) == 1
    v = result.violations[0]
    assert v.kind == "deferred"
    # Replacement lot basis must be rolled up by the disallowed loss ($500).
    rep_lot = next(lot for lot in result.lots if lot.trade_id == "B1")
    assert rep_lot.adjusted_basis == 1100.0 + 500.0
