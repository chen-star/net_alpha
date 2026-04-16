"""CLI integration tests: net-alpha check command."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

from sqlmodel import Session

from net_alpha.cli.app import app
from net_alpha.db.repository import TradeRepository
from net_alpha.models.domain import Trade

DISCLAIMER = "Consult a tax professional"
THIS_YEAR = date.today().year


def _seed_wash_sale_trades(engine, ticker: str = "TSLA", year: int = THIS_YEAR, account: str = "Schwab"):
    """Seed a loss sale + replacement buy that the engine will classify as Confirmed."""
    with Session(engine) as s:
        TradeRepository(s).save_batch(
            [
                Trade(
                    id=str(uuid4()),
                    account=account,
                    date=date(year, 1, 10),
                    ticker=ticker,
                    action="Sell",
                    quantity=10.0,
                    proceeds=2000.0,
                    cost_basis=3000.0,
                ),
                Trade(
                    id=str(uuid4()),
                    account=account,
                    date=date(year, 1, 15),
                    ticker=ticker,
                    action="Buy",
                    quantity=10.0,
                    cost_basis=2200.0,
                ),
            ]
        )
        s.commit()


def test_check_with_violations(cli_setup):
    """Seeded wash sale trades → check finds Confirmed violation, shows disclaimer."""
    runner, engine, _ = cli_setup
    _seed_wash_sale_trades(engine, ticker="TSLA")

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 0, result.output
    assert "Confirmed" in result.output
    assert "TSLA" in result.output
    assert DISCLAIMER in result.output


def test_check_ticker_filter(cli_setup):
    """--ticker TSLA: AAPL violation not shown."""
    runner, engine, _ = cli_setup
    _seed_wash_sale_trades(engine, ticker="TSLA")
    _seed_wash_sale_trades(engine, ticker="AAPL")

    result = runner.invoke(app, ["check", "--ticker", "TSLA"])

    assert result.exit_code == 0, result.output
    assert "TSLA" in result.output
    assert "AAPL" not in result.output


def test_check_year_filter(cli_setup):
    """--year {THIS_YEAR}: next year's violations not shown."""
    runner, engine, _ = cli_setup
    next_year = THIS_YEAR + 1
    _seed_wash_sale_trades(engine, ticker="MSFT", year=THIS_YEAR)
    _seed_wash_sale_trades(engine, ticker="MSFT", year=next_year)

    result = runner.invoke(app, ["check", "--year", str(THIS_YEAR)])

    assert result.exit_code == 0, result.output
    assert str(THIS_YEAR) in result.output
    assert str(next_year) not in result.output


def test_check_no_data(cli_setup):
    """Empty DB: graceful 'no trades' message, exit 0. No disclaimer (early return)."""
    runner, engine, _ = cli_setup

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 0, result.output
    assert "no trades" in result.output.lower() or "import" in result.output.lower()


def test_check_quiet_no_violations(cli_setup):
    runner, engine, settings = cli_setup
    # seed a buy trade (no loss) so there are trades to scan
    with Session(engine) as s:
        TradeRepository(s).save(
            Trade(
                account="schwab",
                date=date(2026, 1, 10),
                ticker="AAPL",
                action="Buy",
                quantity=10,
                proceeds=None,
                cost_basis=1500.0,
            )
        )
        s.commit()

    result = runner.invoke(app, ["check", "--quiet"])
    assert result.exit_code == 0
    assert "0 violations" in result.output
    assert "informational only" in result.output


def test_check_staleness_warning(cli_setup):
    """Account with latest trade > 30 days ago: staleness warning shown."""
    runner, engine, _ = cli_setup

    # Seed a buy from 35 days ago (stale data)
    with Session(engine) as s:
        TradeRepository(s).save(
            Trade(
                id=str(uuid4()),
                account="Schwab",
                date=date.today() - timedelta(days=35),
                ticker="TSLA",
                action="Buy",
                quantity=10.0,
                cost_basis=2200.0,
            )
        )
        s.commit()

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 0, result.output
    # _print_staleness_warnings outputs: "⚠ {account} data last imported {days_ago} days ago."
    assert "days ago" in result.output
