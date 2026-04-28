"""Tests for HarvestOpportunity model and harvest queue computation."""

from __future__ import annotations

from decimal import Decimal

from net_alpha.portfolio.tax_planner import HarvestOpportunity


def test_harvest_opportunity_minimal() -> None:
    """Test creating a minimal HarvestOpportunity instance."""
    opp = HarvestOpportunity(
        symbol="UUUU",
        account_id=1,
        account_label="Schwab Tax",
        qty=Decimal("100"),
        loss=Decimal("-220"),
        lt_st="ST",
        lockout_clear=None,
        premium_offset=None,
        premium_origin_event=None,
        suggested_replacements=[],
    )
    assert opp.symbol == "UUUU"
    assert opp.loss < 0
