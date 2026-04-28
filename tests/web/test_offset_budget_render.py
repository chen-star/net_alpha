from decimal import Decimal

from jinja2 import Environment, FileSystemLoader, select_autoescape

from net_alpha.portfolio.tax_planner import OffsetBudget


def _env():
    return Environment(
        loader=FileSystemLoader("src/net_alpha/web/templates"),
        autoescape=select_autoescape(),
    )


def test_offset_budget_tile_renders_progress() -> None:
    b = OffsetBudget(
        year=2026,
        realized_losses_ytd=Decimal("-1420"),
        realized_gains_ytd=Decimal("0"),
        net_realized=Decimal("-1420"),
        used_against_ordinary=Decimal("1420"),
        carryforward_projection=Decimal("0"),
        planned_delta=Decimal("0"),
    )
    out = _env().get_template("_offset_budget_tile.html").render(budget=b)
    assert "1,420" in out or "1420" in out
    assert "3,000" in out or "3000" in out
    assert "47" in out  # 1420/3000 ≈ 47%


def test_offset_budget_tile_shows_carryforward() -> None:
    b = OffsetBudget(
        year=2026,
        realized_losses_ytd=Decimal("-5000"),
        realized_gains_ytd=Decimal("0"),
        net_realized=Decimal("-5000"),
        used_against_ordinary=Decimal("3000"),
        carryforward_projection=Decimal("2000"),
        planned_delta=Decimal("0"),
    )
    out = _env().get_template("_offset_budget_tile.html").render(budget=b)
    assert "2,000" in out or "2000" in out
    assert "carryforward" in out.lower()


def test_offset_budget_tile_zero_state_friendly() -> None:
    b = OffsetBudget(
        year=2026,
        realized_losses_ytd=Decimal("0"),
        realized_gains_ytd=Decimal("0"),
        net_realized=Decimal("0"),
        used_against_ordinary=Decimal("0"),
        carryforward_projection=Decimal("0"),
        planned_delta=Decimal("0"),
    )
    out = _env().get_template("_offset_budget_tile.html").render(budget=b)
    assert "0" in out
