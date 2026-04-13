from __future__ import annotations

from datetime import date, timedelta

import typer
from rich.console import Console

from net_alpha.cli.output import format_currency, print_disclaimer
from net_alpha.engine.matcher import get_match_confidence, is_within_wash_sale_window

console = Console()

simulate_app = typer.Typer(help="Pre-trade simulation")


@simulate_app.command(name="sell")
def sell_command(
    ticker: str = typer.Argument(help="Ticker to simulate selling"),
    qty: float = typer.Argument(help="Number of shares/contracts"),
    price: float | None = typer.Option(
        None, help="Sale price per share (for dollar impact)"
    ),
) -> None:
    """Simulate selling a position and check for wash sale risk."""
    from net_alpha.cli.app import _bootstrap
    from net_alpha.db.repository import TradeRepository
    from net_alpha.engine.etf_pairs import load_etf_pairs

    settings, session = _bootstrap()
    trade_repo = TradeRepository(session)
    all_trades = trade_repo.list_all()

    user_pairs_path = settings.user_etf_pairs_path
    user_pairs = user_pairs_path if user_pairs_path.exists() else None
    etf_pairs = load_etf_pairs(user_pairs_path=user_pairs)

    today = date.today()
    ticker = ticker.upper()

    console.print()
    if price:
        console.print(
            f"  [bold]SIMULATION: Sell {int(qty)} {ticker} @ "
            f"{format_currency(price)}[/bold]"
        )
    else:
        console.print(f"  [bold]SIMULATION: Sell {int(qty)} {ticker}[/bold]")
    console.print("  " + "\u2500" * 50)

    # Check look-back: any buys of this ticker within last 30 days
    lookback_triggers = _find_lookback_triggers(ticker, today, all_trades, etf_pairs)

    if lookback_triggers:
        # Wash sale WOULD be triggered
        trigger = lookback_triggers[0]  # Most recent
        days_ago = (today - trigger.date).days
        safe = _compute_safe_date([t.date for t in lookback_triggers])
        days_until_safe = (safe - today).days

        estimated_loss = 0.0
        if price:
            # Estimate disallowed loss (rough — uses first buy's basis)
            total_proceeds = price * qty
            avg_basis = (
                sum(t.cost_basis or 0 for t in lookback_triggers)
                / len(lookback_triggers)
            )
            total_qty = sum(t.quantity for t in lookback_triggers)
            estimated_loss = max(
                0, avg_basis * qty / total_qty - total_proceeds
            )
            console.print(
                f"  [red]\u26a0 Wash sale would be triggered — "
                f"{format_currency(estimated_loss)} of this loss would be "
                f"DISALLOWED[/red]"
            )
        else:
            console.print("  [red]\u26a0 Wash sale would be triggered.[/red]")

        confidence = get_match_confidence(
            # Dummy loss sale for confidence check
            _make_dummy_sell(ticker, today, qty),
            trigger,
            etf_pairs,
        )
        console.print()
        console.print(
            f"  Reason: Bought {int(trigger.quantity)} {trigger.ticker} on "
            f"{trigger.account} ({trigger.date}) — {days_ago} days ago "
            f"[{confidence}]"
        )
        console.print(f"  Safe to sell cleanly: {safe} ({days_until_safe} days away)")

        if price and estimated_loss > 0:
            console.print(
                f"  Estimated recoverable loss (if waited): "
                f"{format_currency(estimated_loss)}"
            )
    else:
        # No look-back violation
        safe_rebuy_date = today + timedelta(days=30)

        console.print("  [green]\u2713 No wash sale detected. Safe to sell.[/green]")
        console.print()
        console.print(
            f"  [yellow]\u26a0 Warning: any repurchase of {ticker} before "
            f"{safe_rebuy_date} would trigger a wash sale.[/yellow]"
        )

    print_disclaimer(console)
    session.close()


def _find_lookback_triggers(
    ticker: str,
    sell_date: date,
    all_trades: list,
    etf_pairs: dict[str, list[str]],
) -> list:
    """Find buy trades within the 30-day look-back window for the ticker."""
    triggers = []
    dummy_sell = _make_dummy_sell(ticker, sell_date, 1.0)

    for t in all_trades:
        if not t.is_buy():
            continue
        if not is_within_wash_sale_window(sell_date, t.date):
            continue
        if t.date > sell_date:
            continue  # Look-back only (before sell date)
        confidence = get_match_confidence(dummy_sell, t, etf_pairs)
        if confidence is not None:
            triggers.append(t)

    triggers.sort(key=lambda t: t.date, reverse=True)
    return triggers


def _compute_safe_date(buy_dates: list[date]) -> date:
    """Compute the earliest safe sell date (30 days after the latest buy)."""
    latest = max(buy_dates)
    return latest + timedelta(days=30)


def _make_dummy_sell(ticker: str, sell_date: date, qty: float):
    """Create a dummy sell trade for confidence matching."""
    from net_alpha.models.domain import Trade

    return Trade(
        account="__simulation__",
        date=sell_date,
        ticker=ticker,
        action="Sell",
        quantity=qty,
        proceeds=0.0,
        cost_basis=1.0,  # Ensure is_loss() is True
    )
