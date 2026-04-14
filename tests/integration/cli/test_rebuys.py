"""CLI integration tests: net-alpha rebuys command."""
from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlmodel import Session

from net_alpha.cli.app import app
from net_alpha.db.repository import TradeRepository, ViolationRepository
from net_alpha.models.domain import Trade, WashSaleViolation

DISCLAIMER = "Consult a tax professional"
TODAY = date.today()


def _seed_loss(engine, ticker: str, sell_days_ago: int, quantity: float = 10.0) -> str:
    """Seed a loss sale trade. Returns the trade id."""
    trade_id = str(uuid4())
    sell_date = TODAY - timedelta(days=sell_days_ago)
    with Session(engine) as s:
        TradeRepository(s).save(Trade(
            id=trade_id, account="Schwab", date=sell_date,
            ticker=ticker, action="Sell", quantity=quantity,
            proceeds=quantity * 200.0, cost_basis=quantity * 300.0,
        ))
        s.commit()
    return trade_id


def _seed_violation(engine, loss_trade_id: str, matched_qty: float):
    """Seed a violation matching some quantity of the loss trade."""
    with Session(engine) as s:
        replace_id = str(uuid4())
        replace_date = TODAY - timedelta(days=5)
        TradeRepository(s).save(Trade(
            id=replace_id, account="Schwab", date=replace_date,
            ticker="X", action="Buy", quantity=matched_qty, cost_basis=matched_qty * 220.0,
        ))
        ViolationRepository(s).save(WashSaleViolation(
            id=str(uuid4()),
            loss_trade_id=loss_trade_id,
            replacement_trade_id=replace_id,
            confidence="Confirmed",
            disallowed_loss=matched_qty * 100.0,
            matched_quantity=matched_qty,
        ))
        s.commit()


def test_rebuys_open_window(cli_setup):
    """Loss sale 10 days ago, no match → ticker shown, 20 days remaining."""
    runner, engine, _ = cli_setup
    _seed_loss(engine, "TSLA", sell_days_ago=10)

    result = runner.invoke(app, ["rebuys"])

    assert result.exit_code == 0, result.output
    assert "TSLA" in result.output
    assert "20 days" in result.output
    assert DISCLAIMER in result.output


def test_rebuys_cleared_window(cli_setup):
    """Loss sale 35 days ago → window closed, AAPL not shown."""
    runner, engine, _ = cli_setup
    _seed_loss(engine, "AAPL", sell_days_ago=35)

    result = runner.invoke(app, ["rebuys"])

    assert result.exit_code == 0, result.output
    assert "AAPL" not in result.output


def test_rebuys_partial_match(cli_setup):
    """Loss 10 shares, 4 matched → '6/10' open qty shown."""
    runner, engine, _ = cli_setup
    loss_id = _seed_loss(engine, "MSFT", sell_days_ago=10, quantity=10.0)
    _seed_violation(engine, loss_id, matched_qty=4.0)

    result = runner.invoke(app, ["rebuys"])

    assert result.exit_code == 0, result.output
    assert "MSFT" in result.output
    assert "6/10" in result.output


def test_rebuys_empty(cli_setup):
    """No loss sales in open window → 'All clear' message, exit 0."""
    runner, engine, _ = cli_setup

    result = runner.invoke(app, ["rebuys"])

    assert result.exit_code == 0, result.output
    # rebuys_command prints: "No positions currently in wash sale window. All clear."
    assert "all clear" in result.output.lower() or "no positions" in result.output.lower()
    assert DISCLAIMER in result.output
