"""Tests for tax_planner.build_plan."""
from datetime import date
from decimal import Decimal

from net_alpha.portfolio.tax_planner import (
    HarvestOpportunity,
    TaxBrackets,
    build_plan,
    summarize_manual_picks,
)


def _row(symbol, loss, lt_st="ST", lockout_clear=None, account="schwab/personal"):
    return HarvestOpportunity(
        symbol=symbol,
        account_id=1,
        account_label=account,
        qty=Decimal("10"),
        open_basis=Decimal("100") + abs(Decimal(str(loss))),
        loss=Decimal(str(loss)),
        lt_st=lt_st,
        lockout_clear=lockout_clear,
        premium_offset=None,
        premium_origin_event=None,
        suggested_replacements=[],
    )


def _rates():
    return TaxBrackets(
        filing_status="single",
        state="CA",
        federal_marginal_rate=Decimal("0.24"),
        state_marginal_rate=Decimal("0.093"),
        ltcg_rate=Decimal("0.15"),
        qualified_div_rate=Decimal("0.15"),
    )


def test_auto_budget_includes_realized_gains_plus_3000():
    rows = [_row("A", -100), _row("B", -200)]
    plan = build_plan(rows, realized_gains_ytd=Decimal("5000"), marginal_rates=_rates())
    assert plan.target_budget == Decimal("8000")
    assert plan.used_auto_budget is True


def test_auto_budget_with_no_realized_gains():
    rows = [_row("A", -100)]
    plan = build_plan(rows, realized_gains_ytd=Decimal("0"), marginal_rates=_rates())
    assert plan.target_budget == Decimal("3000")


def test_auto_budget_with_negative_realized_gains_uses_3000():
    rows = [_row("A", -100)]
    plan = build_plan(rows, realized_gains_ytd=Decimal("-1500"), marginal_rates=_rates())
    assert plan.target_budget == Decimal("3000")


def test_custom_budget_overrides_auto():
    rows = [_row("A", -100), _row("B", -200), _row("C", -500)]
    plan = build_plan(
        rows,
        realized_gains_ytd=Decimal("10000"),
        marginal_rates=_rates(),
        target_budget=Decimal("400"),
    )
    assert plan.target_budget == Decimal("400")
    assert plan.used_auto_budget is False
    # Greedy by tax-saved descending: C(500) is first and overshoots budget=400 → stop.
    # No skip-and-continue: B and A are never considered.
    assert plan.selected == []
    assert plan.total_loss_harvested == Decimal("0")


def test_st_first_tie_break():
    rows = [
        _row("LT_LOSS", -100, lt_st="LT"),
        _row("ST_LOSS", -100, lt_st="ST"),
    ]
    flat = TaxBrackets(
        filing_status="single",
        state="",
        federal_marginal_rate=Decimal("0"),
        state_marginal_rate=Decimal("0"),
        ltcg_rate=Decimal("0"),
        qualified_div_rate=Decimal("0"),
    )
    plan = build_plan(
        rows,
        realized_gains_ytd=Decimal("0"),
        marginal_rates=flat,
        target_budget=Decimal("100"),
    )
    assert plan.selected[0].symbol == "ST_LOSS"


def test_no_marginal_rates_ranks_by_abs_loss():
    rows = [_row("A", -100), _row("B", -300), _row("C", -50)]
    plan = build_plan(
        rows,
        realized_gains_ytd=Decimal("0"),
        marginal_rates=None,
        target_budget=Decimal("400"),
    )
    assert [c.symbol for c in plan.selected] == ["B", "A"]


def test_all_locked_excluded_when_default():
    rows = [
        _row("A", -100, lockout_clear=date(2030, 1, 1)),
        _row("B", -100, lockout_clear=date(2030, 1, 1)),
    ]
    plan = build_plan(rows, realized_gains_ytd=Decimal("0"), marginal_rates=_rates())
    assert plan.selected == []
    assert {c.symbol for c in plan.skipped_locked} == {"A", "B"}


def test_locked_included_when_exclude_locked_false():
    rows = [_row("A", -100, lockout_clear=date(2030, 1, 1))]
    plan = build_plan(
        rows,
        realized_gains_ytd=Decimal("0"),
        marginal_rates=_rates(),
        exclude_locked=False,
    )
    assert len(plan.selected) == 1


def test_empty_candidates():
    plan = build_plan([], realized_gains_ytd=Decimal("0"), marginal_rates=_rates())
    assert plan.selected == []
    assert plan.total_loss_harvested == Decimal("0")
    assert plan.estimated_tax_saved == Decimal("0")


def test_single_candidate_exceeds_budget_yields_empty():
    rows = [_row("A", -1000)]
    plan = build_plan(
        rows,
        realized_gains_ytd=Decimal("0"),
        marginal_rates=_rates(),
        target_budget=Decimal("100"),
    )
    assert plan.selected == []


def test_greedy_stops_on_first_overshoot_no_skip():
    # A's tax_saved (333) > B's tax_saved (33.3), so A is checked first.
    # A overshoots target=250; we stop. B is NOT considered.
    rows = [_row("A", -300), _row("B", -100)]
    plan = build_plan(
        rows,
        realized_gains_ytd=Decimal("0"),
        marginal_rates=_rates(),
        target_budget=Decimal("250"),
    )
    assert plan.selected == []


def test_ordinary_offset_capped_at_3000():
    rows = [_row("A", -10000)]
    plan = build_plan(
        rows,
        realized_gains_ytd=Decimal("0"),
        marginal_rates=_rates(),
        target_budget=Decimal("10000"),
    )
    assert plan.ordinary_offset_used == Decimal("3000")
    assert plan.gain_offset_used == Decimal("7000")
    assert plan.total_loss_harvested == Decimal("10000")


def test_summarize_manual_picks_uses_explicit_selection():
    rows = [_row("A", -100), _row("B", -200), _row("C", -300)]
    picks = [("A", "schwab/personal"), ("C", "schwab/personal")]
    plan = summarize_manual_picks(
        picks=picks,
        candidates=rows,
        realized_gains_ytd=Decimal("0"),
        marginal_rates=_rates(),
    )
    syms = {c.symbol for c in plan.selected}
    assert syms == {"A", "C"}
    assert plan.total_loss_harvested == Decimal("400")
    assert plan.used_auto_budget is False


def test_summarize_manual_picks_unknown_pick_silently_dropped():
    rows = [_row("A", -100)]
    plan = summarize_manual_picks(
        picks=[("A", "schwab/personal"), ("ZZZ", "schwab/personal")],
        candidates=rows,
        realized_gains_ytd=Decimal("0"),
        marginal_rates=_rates(),
    )
    assert {c.symbol for c in plan.selected} == {"A"}


def test_summarize_manual_picks_empty_selection():
    rows = [_row("A", -100), _row("B", -200)]
    plan = summarize_manual_picks(
        picks=[],
        candidates=rows,
        realized_gains_ytd=Decimal("5000"),
        marginal_rates=_rates(),
    )
    assert plan.selected == []
    assert plan.total_loss_harvested == Decimal("0")
    assert plan.estimated_tax_saved == Decimal("0")


def test_summarize_manual_picks_caps_ordinary_offset():
    rows = [_row("BIG", -10000)]
    plan = summarize_manual_picks(
        picks=[("BIG", "schwab/personal")],
        candidates=rows,
        realized_gains_ytd=Decimal("0"),
        marginal_rates=_rates(),
    )
    assert plan.ordinary_offset_used == Decimal("3000")
    assert plan.gain_offset_used == Decimal("7000")
