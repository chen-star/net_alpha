from datetime import date
from decimal import Decimal

from jinja2 import Environment, FileSystemLoader, select_autoescape

from net_alpha.portfolio.tax_planner import CSPAssigned, HarvestOpportunity


def _env():
    return Environment(
        loader=FileSystemLoader("src/net_alpha/web/templates"),
        autoescape=select_autoescape(),
    )


def test_harvest_queue_renders_loss_amounts() -> None:
    rows = [
        HarvestOpportunity(
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
