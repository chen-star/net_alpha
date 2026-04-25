from datetime import date, datetime
from decimal import Decimal

from net_alpha.models.domain import (
    Account,
    ImportSummary,
    SimulationOption,
    WashSaleViolation,
)


def test_disclaimer_render_returns_required_string():
    from net_alpha.output.disclaimer import render

    assert "informational" in render().lower()
    assert "tax professional" in render().lower()


def test_watch_list_renders_violations_and_open_windows():
    from net_alpha.output.watch_list import render

    v = WashSaleViolation(
        loss_trade_id="1",
        replacement_trade_id="2",
        confidence="Confirmed",
        disallowed_loss=1243.0,
        matched_quantity=10,
        loss_account="schwab/personal",
        buy_account="schwab/roth",
        loss_sale_date=date(2024, 9, 15),
        triggering_buy_date=date(2024, 9, 22),
    )
    out = render(lots=[], violations=[v], today=date(2024, 9, 30))
    assert "TSLA" in out or "TRIGGERED" in out


def test_ytd_impact_renders_total_and_count():
    from net_alpha.output.ytd_impact import render

    v = WashSaleViolation(
        loss_trade_id="1",
        replacement_trade_id="2",
        confidence="Confirmed",
        disallowed_loss=1243.0,
        matched_quantity=10,
        loss_account="schwab/personal",
        buy_account="schwab/roth",
        loss_sale_date=date(2024, 9, 15),
        triggering_buy_date=date(2024, 9, 22),
    )
    out = render(violations=[v], year=2024)
    assert "1,243" in out or "1243" in out
    assert "2024" in out


def test_sim_result_renders_one_section_per_option():
    from net_alpha.output.sim_result import render

    p = Account(id=1, broker="schwab", label="personal")
    r = Account(id=2, broker="schwab", label="roth")
    options = [
        SimulationOption(
            account=p,
            lots_consumed_fifo=[],
            realized_pnl=Decimal("-150"),
            would_trigger_wash_sale=True,
            blocking_buys=[],
            lookforward_block_until=None,
            confidence="Confirmed",
            insufficient_shares=False,
            available_shares=Decimal("10"),
        ),
        SimulationOption(
            account=r,
            lots_consumed_fifo=[],
            realized_pnl=Decimal("300"),
            would_trigger_wash_sale=False,
            blocking_buys=[],
            lookforward_block_until=None,
            confidence="N/A",
            insufficient_shares=False,
            available_shares=Decimal("10"),
        ),
    ]
    out = render(ticker="TSLA", qty=Decimal("10"), price=Decimal("180"), options=options)
    assert "OPTION A" in out and "OPTION B" in out
    assert "schwab/personal" in out and "schwab/roth" in out


def test_imports_table_renders_one_row_per_summary():
    from net_alpha.output.imports_table import render

    s = ImportSummary(
        id=1,
        account_display="schwab/personal",
        csv_filename="q1.csv",
        trade_count=412,
        imported_at=datetime(2026, 4, 25, 10, 0),
    )
    out = render([s])
    assert "q1.csv" in out and "412" in out and "schwab/personal" in out
