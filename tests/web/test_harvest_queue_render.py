from datetime import date
from decimal import Decimal

from jinja2 import Environment, FileSystemLoader, select_autoescape

from net_alpha.portfolio.tax_planner import CSPAssigned, HarvestOpportunity


def _env():
    from net_alpha.web.format import dom_id_slug

    env = Environment(
        loader=FileSystemLoader("src/net_alpha/web/templates"),
        autoescape=select_autoescape(),
    )
    env.filters["dom_id_slug"] = dom_id_slug
    return env


def _opp(symbol, account_label, loss, *, lt_st="ST", tax_saved=None):
    return HarvestOpportunity(
        symbol=symbol,
        account_id=1,
        account_label=account_label,
        qty=Decimal("10"),
        open_basis=Decimal("1000"),
        loss=Decimal(str(loss)),
        lt_st=lt_st,
        lockout_clear=None,
        premium_offset=None,
        premium_origin_event=None,
        suggested_replacements=[],
        estimated_tax_saved=(Decimal(str(tax_saved)) if tax_saved is not None else None),
    )


def test_harvest_plan_tax_saved_is_per_lot_not_collapsed_by_symbol():
    """Two loss lots of the same symbol+account must each show their OWN
    tax-saved value. Regression for the dict-keyed-by-(symbol,account) bug
    that stamped one lot's value onto every lot of the symbol.
    """
    big = _opp("HIMS", "schwab/st", -740.66, tax_saved="335.52")
    small = _opp("HIMS", "schwab/st", -40.50, tax_saved="18.35")
    rows = [big, small]
    out = (
        _env()
        .get_template("_harvest_plan.html")
        .render(
            plan=type(
                "P",
                (),
                {
                    "selected": [],
                    "skipped_locked": [],
                    "realized_gains_ytd": Decimal("0"),
                    "ordinary_offset_used": Decimal("0"),
                    "gain_offset_used": Decimal("0"),
                    "total_loss_harvested": Decimal("0"),
                    "estimated_tax_saved": Decimal("0"),
                    "target_budget": Decimal("0"),
                    "used_auto_budget": True,
                },
            )(),
            rows=rows,
            rows_page=rows,
            start_idx=0,
            selected_keys=set(),
            mode="auto",
            custom_budget="",
            exclude_locked=True,
            has_tax_config=True,
            pagination={
                "page": 1,
                "page_size": 25,
                "total_pages": 1,
                "total_rows": 2,
                "page_size_options": (10, 25, 50, 100),
            },
            picks=[],
            account_filter_active=False,
            selected_accounts=[],
            oob_cells="",
        )
    )
    # Both distinct per-lot values must be present.
    assert "335.52" in out, "large-loss lot's own tax-saved value must render"
    assert "18.35" in out, "small-loss lot's own tax-saved value must render"
    # The tax-saved cell DOM ids must be unique (no duplicate element ids).
    import re

    ids = re.findall(r'id="tax-saved-[^"]+"', out)
    assert len(ids) == len(set(ids)), f"duplicate tax-saved cell ids: {ids}"


def test_harvest_queue_renders_loss_amounts() -> None:
    rows = [
        HarvestOpportunity(
            symbol="UUUU",
            account_id=1,
            account_label="Schwab Tax",
            qty=Decimal("100"),
            open_basis=Decimal("320"),  # 100 shares * $3.20/share basis
            loss=Decimal("-220"),
            lt_st="ST",
            lockout_clear=None,
            premium_offset=None,
            premium_origin_event=None,
            suggested_replacements=[],
        )
    ]
    env = _env()
    out = env.get_template("_harvest_queue.html").render(rows=rows, only_harvestable=False)
    assert "UUUU" in out
    assert "220" in out
    assert "ST" in out


def test_harvest_queue_renders_lockout_clear_when_present() -> None:
    rows = [
        HarvestOpportunity(
            symbol="UUUU",
            account_id=1,
            account_label="Schwab Tax",
            qty=Decimal("100"),
            open_basis=Decimal("320"),  # 100 shares * $3.20/share basis
            loss=Decimal("-220"),
            lt_st="ST",
            lockout_clear=date(2026, 5, 16),
            premium_offset=None,
            premium_origin_event=None,
            suggested_replacements=[],
        )
    ]
    out = _env().get_template("_harvest_queue.html").render(rows=rows, only_harvestable=False)
    assert "2026-05-16" in out


def test_harvest_queue_renders_premium_offset_for_csp_origin() -> None:
    rows = [
        HarvestOpportunity(
            symbol="UUUU",
            account_id=1,
            account_label="Schwab Tax",
            qty=Decimal("100"),
            open_basis=Decimal("320"),  # 100 shares * $3.20/share basis
            loss=Decimal("-220"),
            lt_st="ST",
            lockout_clear=None,
            premium_offset=Decimal("120"),
            premium_origin_event=CSPAssigned(
                option_natural_key="UUUU 09/19/2025 5.00 P",
                premium_received=Decimal("120"),
                strike=Decimal("5"),
                assignment_date=date(2025, 9, 19),
            ),
            suggested_replacements=[],
        )
    ]
    out = _env().get_template("_harvest_queue.html").render(rows=rows, only_harvestable=False)
    assert "CSP" in out or "premium" in out.lower()
    assert "120" in out


def test_harvest_queue_empty_state() -> None:
    out = _env().get_template("_harvest_queue.html").render(rows=[], only_harvestable=False)
    assert "no harvest" in out.lower() or "no losses" in out.lower() or "nothing" in out.lower()
