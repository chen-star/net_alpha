from __future__ import annotations

from decimal import Decimal

from jinja2 import Environment, FileSystemLoader, select_autoescape

from net_alpha.portfolio.tax_planner import TaxProjection


def _env():
    return Environment(
        loader=FileSystemLoader("src/net_alpha/web/templates"),
        autoescape=select_autoescape(),
    )


def test_projection_card_renders_total_and_breakdown() -> None:
    p = TaxProjection(
        year=2026,
        realized_st_gain=Decimal("10000"),
        realized_lt_gain=Decimal("0"),
        qualified_div=Decimal("0"),
        ordinary_div=Decimal("0"),
        interest_income=Decimal("0"),
        federal_tax=Decimal("3200"),
        state_tax=Decimal("930"),
        total_tax=Decimal("4130"),
    )
    out = _env().get_template("_projection_card.html").render(projection=p, has_tax_config=True)
    assert "4,130" in out
    assert "3,200" in out
    assert "930" in out


def test_projection_card_placeholder_when_config_missing() -> None:
    """Placeholder explains why the projection is empty (Pr2: no self-referential link)."""
    out = _env().get_template("_projection_card.html").render(projection=None, has_tax_config=False)
    # Placeholder should give the user something actionable to read.
    assert "filing status" in out.lower() or "tax rates" in out.lower()
    # Pr2: the card no longer links to /tax?view=projection (self-referential cross-ref removed).
    # Instead it directs the user to the inline form below the card.
    assert "form below" in out.lower()
