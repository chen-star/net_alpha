"""Hypothesis-driven invariant tests.

These run the same OV-*, AL-*, PL-*, XP-1 checks against generated portfolio
shapes that no hand-written test would think of. The same invariant functions
are used at L1 render-time, so any divergence between "what looks right" and
"what's mathematically required" surfaces here.
"""

from __future__ import annotations

from dataclasses import dataclass

from hypothesis import given, settings
from hypothesis import strategies as st

from net_alpha.verify.invariants import (
    check_al1_allocation_sums_to_100,
    check_ov1_total_market_value,
    check_ov2_unrealized_consistency,
    check_pl1_value_consistency,
    check_pl2_pnl_consistency,
)
from net_alpha.verify.tolerances import Severity, Tolerance


@dataclass
class _Lot:
    id: int
    qty: float
    current_price: float
    market_value: float
    adjusted_basis: float
    unrealized_pl: float


_lot_strategy = st.builds(
    lambda qid, qty, price, basis: _Lot(
        id=qid,
        qty=qty,
        current_price=price,
        market_value=round(qty * price, 2),
        adjusted_basis=basis,
        unrealized_pl=round(qty * price - basis, 2),
    ),
    qid=st.integers(min_value=1, max_value=10000),
    qty=st.floats(min_value=0.01, max_value=10000, allow_nan=False, allow_infinity=False).map(lambda x: round(x, 4)),
    price=st.floats(min_value=0.01, max_value=10000, allow_nan=False, allow_infinity=False).map(lambda x: round(x, 2)),
    basis=st.floats(min_value=0.01, max_value=1e7, allow_nan=False, allow_infinity=False).map(lambda x: round(x, 2)),
)


# Wider than production to absorb compounded float rounding (price * qty over
# many lots accumulates more error than a single per-lot check).
_TOL = Tolerance(abs=0.10, rel=0.001)


@given(lots=st.lists(_lot_strategy, min_size=0, max_size=50))
@settings(max_examples=50, deadline=None)
def test_property_ov1_holds_when_total_matches_sum(lots):
    total = sum(lot.market_value for lot in lots)
    result = check_ov1_total_market_value(total_market_value=total, lots=lots, tol=_TOL)
    assert result.severity == Severity.OK, (result.rule_id, result.ours, result.theirs, result.delta)


@given(
    total_mv=st.floats(min_value=0, max_value=1e6, allow_nan=False).map(lambda x: round(x, 2)),
    total_basis=st.floats(min_value=0, max_value=1e6, allow_nan=False).map(lambda x: round(x, 2)),
)
@settings(max_examples=50, deadline=None)
def test_property_ov2_holds_when_unrealized_is_exact(total_mv, total_basis):
    unrealized = round(total_mv - total_basis, 2)
    result = check_ov2_unrealized_consistency(
        total_market_value=total_mv,
        total_basis=total_basis,
        unrealized_pl=unrealized,
        tol=_TOL,
    )
    assert result.severity == Severity.OK, (result.rule_id, result.ours, result.theirs, result.delta)


@given(
    rows=st.lists(
        st.tuples(
            st.text(alphabet=st.characters(min_codepoint=65, max_codepoint=90), min_size=1, max_size=4),
            st.floats(min_value=0.01, max_value=100, allow_nan=False).map(lambda x: round(x, 4)),
        ),
        min_size=1,
        max_size=20,
    ),
)
@settings(max_examples=50, deadline=None)
def test_property_al1_can_be_normalized_to_100(rows):
    # Renormalize the pct column so the test setup itself doesn't trigger failures.
    total = sum(p for _, p in rows)
    if total == 0:
        return
    normalized = [(s, p * 100 / total) for s, p in rows]
    result = check_al1_allocation_sums_to_100(
        allocation_rows=normalized,
        tol=Tolerance(abs=0.05, rel=0.001),
    )
    assert result.severity == Severity.OK, (result.rule_id, result.ours, result.theirs, result.delta)


@given(lots=st.lists(_lot_strategy, min_size=1, max_size=30))
@settings(max_examples=50, deadline=None)
def test_property_pl1_holds_for_clean_rows(lots):
    rows = [
        {"id": lot.id, "qty": lot.qty, "current_price": lot.current_price, "market_value": lot.market_value}
        for lot in lots
    ]
    results = check_pl1_value_consistency(lot_rows=rows, tol=_TOL)
    assert all(r.severity == Severity.OK for r in results), [
        (r.rule_id, r.severity, r.ours, r.theirs, r.delta) for r in results if r.severity != Severity.OK
    ]


@given(lots=st.lists(_lot_strategy, min_size=1, max_size=30))
@settings(max_examples=50, deadline=None)
def test_property_pl2_holds_for_clean_rows(lots):
    rows = [
        {
            "id": lot.id,
            "market_value": lot.market_value,
            "adjusted_basis": lot.adjusted_basis,
            "unrealized_pl": lot.unrealized_pl,
        }
        for lot in lots
    ]
    results = check_pl2_pnl_consistency(lot_rows=rows, tol=_TOL)
    assert all(r.severity == Severity.OK for r in results), [
        (r.rule_id, r.severity, r.ours, r.theirs, r.delta) for r in results if r.severity != Severity.OK
    ]
