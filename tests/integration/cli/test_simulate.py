"""CLI integration tests: net-alpha simulate sell command."""
from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

from sqlmodel import Session

from net_alpha.cli.app import app
from net_alpha.db.repository import TradeRepository
from net_alpha.models.domain import Trade

DISCLAIMER = "Consult a tax professional"
TODAY = date.today()


def _seed_buy(
    engine, ticker: str, days_ago: int, quantity: float = 10.0, cost_basis: float = 2500.0, account: str = "Schwab"
):
    with Session(engine) as s:
        TradeRepository(s).save(Trade(
            id=str(uuid4()), account=account,
            date=TODAY - timedelta(days=days_ago),
            ticker=ticker, action="Buy", quantity=quantity, cost_basis=cost_basis,
        ))
        s.commit()


def test_simulate_safe(cli_setup):
    """No TSLA buys in last 30 days → 'Safe to sell' message."""
    runner, engine, _ = cli_setup
    _seed_buy(engine, "TSLA", days_ago=35)  # outside window

    result = runner.invoke(app, ["simulate", "sell", "TSLA", "10"])

    assert result.exit_code == 0, result.output
    assert "safe to sell" in result.output.lower()
    assert DISCLAIMER in result.output


def test_simulate_risky_no_price(cli_setup):
    """TSLA buy 5 days ago → wash sale warning and safe rebuy date shown."""
    runner, engine, _ = cli_setup
    _seed_buy(engine, "TSLA", days_ago=5)

    result = runner.invoke(app, ["simulate", "sell", "TSLA", "10"])

    assert result.exit_code == 0, result.output
    # "⚠ Wash sale would be triggered." and safe date
    assert "wash sale" in result.output.lower() or "triggered" in result.output.lower()
    safe_date = (TODAY - timedelta(days=5) + timedelta(days=30)).isoformat()
    assert safe_date in result.output
    assert DISCLAIMER in result.output


def test_simulate_risky_with_price(cli_setup):
    """TSLA buy 5 days ago at $250/share + --price 200 → disallowed loss shown."""
    runner, engine, _ = cli_setup
    # 10 shares at $250/share = cost_basis $2500
    _seed_buy(engine, "TSLA", days_ago=5, quantity=10.0, cost_basis=2500.0)

    result = runner.invoke(app, ["simulate", "sell", "TSLA", "10", "--price", "200"])

    assert result.exit_code == 0, result.output
    # Estimated disallowed: max(0, 2500 * 10/10 - 200*10) = max(0, 2500-2000) = $500
    assert "DISALLOWED" in result.output or "disallowed" in result.output.lower()
    assert DISCLAIMER in result.output


def test_simulate_etf_risky(cli_setup):
    """VOO buy 10 days ago; simulating SPY sell → Unclear ETF wash sale risk."""
    runner, engine, _ = cli_setup
    _seed_buy(engine, "VOO", days_ago=10)

    result = runner.invoke(app, ["simulate", "sell", "SPY", "10"])

    assert result.exit_code == 0, result.output
    # Confidence "Unclear" shown next to the VOO trigger
    assert "Unclear" in result.output
    assert DISCLAIMER in result.output
