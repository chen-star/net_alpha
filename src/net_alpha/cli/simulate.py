from __future__ import annotations

import difflib
from datetime import date, timedelta

import typer
from rich.console import Console
from rich.table import Table

from net_alpha.cli.output import format_currency, print_disclaimer
from net_alpha.engine.matcher import get_match_confidence, is_within_wash_sale_window

console = Console()

simulate_app = typer.Typer(help="Pre-trade simulation")


def _suggest_ticker(ticker: str, known_tickers: list[str]) -> str | None:
    """Return a close-match suggestion for a possibly mistyped ticker, or None."""
    if ticker in known_tickers:
        return None
    matches = difflib.get_close_matches(ticker, known_tickers, n=1, cutoff=0.6)
    return matches[0] if matches else None


@simulate_app.command(name="sell")
def sell_command(
    ticker: str = typer.Argument(help="Ticker to simulate selling"),
    qty: float = typer.Argument(help="Number of shares/contracts"),
    price: float | None = typer.Option(None, help="Sale price per share (for dollar impact)"),
) -> None:
    """Simulate selling a position and check for wash sale risk."""
    all_trades, etf_pairs, session = _bootstrap_and_load()

    today = date.today()
    ticker = ticker.upper()

    console.print()
    if price:
        console.print(f"  [bold]SIMULATION: Sell {int(qty)} {ticker} @ {format_currency(price)}[/bold]")
    else:
        console.print(f"  [bold]SIMULATION: Sell {int(qty)} {ticker}[/bold]")
    console.print("  " + "\u2500" * 50)

    # Validate ticker exists in known open lots (or has ETF-equivalent lots)
    from net_alpha.engine.tax_position import identify_open_lots
    open_lots = identify_open_lots(all_trades, as_of=today)
    known_tickers = list({lot.ticker for lot in open_lots})

    # Build set of all tickers reachable via ETF pairs
    etf_group = {ticker}
    for group in etf_pairs.values():
        if ticker in group:
            etf_group.update(group)

    has_lots = bool(etf_group & set(known_tickers))
    if not has_lots:
        suggestion = _suggest_ticker(ticker, known_tickers)
        if suggestion:
            console.print(
                f"  [red]Error:[/red] No open lots for '{ticker}'. "
                f"Did you mean: [bold]{suggestion}[/bold]?"
            )
        else:
            console.print(f"  [red]Error:[/red] No open lots for '{ticker}'.")
        console.print(
            "  [dim]\u2192 Run net-alpha tax-position to see all open positions.[/dim]"
        )
        if session:
            session.close()
        raise typer.Exit(1)

    # Check look-back: any buys of this ticker within last 30 days
    lookback_triggers = _find_lookback_triggers(ticker, today, all_trades, etf_pairs)

    if lookback_triggers:
        trigger = lookback_triggers[0]
        days_ago = (today - trigger.date).days
        safe = _compute_safe_date([t.date for t in lookback_triggers])
        days_until_safe = (safe - today).days

        estimated_loss = 0.0
        if price:
            total_proceeds = price * qty
            avg_basis = sum(t.cost_basis or 0 for t in lookback_triggers) / len(lookback_triggers)
            total_qty = sum(t.quantity for t in lookback_triggers)
            estimated_loss = max(0, avg_basis * qty / total_qty - total_proceeds)
            console.print(
                f"  [red]\u26a0 Wash sale would be triggered — "
                f"{format_currency(estimated_loss)} of this loss would be "
                f"DISALLOWED[/red]"
            )
        else:
            console.print("  [red]\u26a0 Wash sale would be triggered.[/red]")

        confidence = get_match_confidence(
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
            console.print(f"  Estimated recoverable loss (if waited): {format_currency(estimated_loss)}")
    else:
        safe_rebuy_date = today + timedelta(days=30)

        console.print("  [green]\u2713 No wash sale detected. Safe to sell.[/green]")
        console.print()
        console.print(
            f"  [yellow]\u26a0 Warning: any repurchase of {ticker} before "
            f"{safe_rebuy_date} would trigger a wash sale.[/yellow]"
        )

    # Lot selection table (only when price provided)
    if price:
        _render_lot_selection(ticker, qty, price, all_trades, etf_pairs, lookback_triggers, today)

    print_disclaimer(console)
    if session:
        session.close()


def _bootstrap_and_load() -> tuple[list, dict, object]:
    """Load trades and ETF pairs from DB. Returns (trades, etf_pairs, session)."""
    from net_alpha.cli.app import _bootstrap
    from net_alpha.db.repository import TradeRepository
    from net_alpha.engine.etf_pairs import load_etf_pairs

    settings, session = _bootstrap()
    trade_repo = TradeRepository(session)
    all_trades = trade_repo.list_all()

    user_pairs_path = settings.user_etf_pairs_path
    etf_pairs = load_etf_pairs(user_pairs_path=user_pairs_path)

    return all_trades, etf_pairs, session


def _render_lot_selection(
    ticker: str,
    qty: float,
    price: float,
    all_trades: list,
    etf_pairs: dict,
    lookback_triggers: list,
    today: date,
) -> None:
    """Render lot selection comparison table and recommendation."""
    selections, recommendation = _get_lot_selection_data(
        ticker, qty, price, all_trades, lookback_triggers, etf_pairs, today
    )

    if selections is None:
        console.print()
        console.print(f"  No open lots for {ticker}. Nothing to select.")
        return

    console.print()
    console.print(f"  [bold]LOT SELECTION \u2014 {ticker} {int(qty)} shares @ {format_currency(price)}[/bold]")
    console.print("  " + "\u2500" * 50)

    table = Table(box=None, padding=(0, 2), show_edge=False)
    table.add_column("Method")
    table.add_column("Lot Date")
    table.add_column("Qty", justify="right")
    table.add_column("Basis/sh", justify="right")
    table.add_column("Gain/Loss", justify="right")
    table.add_column("Treatment")
    table.add_column("Wash Sale")

    for method in ("FIFO", "HIFO", "LIFO"):
        sel = selections.get(method)
        if sel is None:
            continue

        for i, lot in enumerate(sel.lots_used):
            treatment_parts = []
            if sel.st_gain_loss != 0:
                treatment_parts.append("Short-term")
            if sel.lt_gain_loss != 0:
                treatment_parts.append("Long-term")
            treatment = " + ".join(treatment_parts) if treatment_parts else "Short-term"

            wash_str = "\u26a0 Risk" if sel.wash_sale_risk else "None"

            gain_loss_str = format_currency(sel.total_gain_loss)
            if sel.total_gain_loss > 0:
                gain_loss_str = f"+{gain_loss_str}"

            table.add_row(
                method if i == 0 else "",
                str(lot.purchase_date),
                str(int(lot.quantity)),
                format_currency(lot.adjusted_basis_per_share),
                gain_loss_str if i == 0 else "",
                treatment if i == 0 else "",
                wash_str if i == 0 else "",
            )

    console.print(table)

    if recommendation:
        _render_recommendation(recommendation, selections)


def _render_recommendation(rec, selections: dict) -> None:
    """Render the recommendation text from structured LotRecommendation."""
    console.print()
    console.print("  [bold]Recommendation[/bold] (given your YTD position):")

    reason_text = {
        "st_loss_offset": "produces a short-term loss to offset your gains",
        "lt_lower_rate": "produces a long-term gain (lower tax rate)",
        "least_gain": "produces the least additional gain",
    }

    preferred = rec.preferred_method
    reason = reason_text.get(rec.reason, rec.reason)

    if rec.has_wash_risk:
        console.print(f"    \u2192 {preferred} {reason} \u2014 but wash sale risk detected.")
        if rec.safe_sell_date:
            console.print(f"      Wait until {rec.safe_sell_date} to sell cleanly using {preferred}.")
        if rec.fallback_method:
            fallback_reason = reason_text.get(rec.fallback_reason, rec.fallback_reason)
            console.print(f"    \u2192 Best clean option: {rec.fallback_method} \u2014 {fallback_reason}.")
        else:
            console.print("    \u2192 No clean option available \u2014 all methods carry wash sale risk.")
    else:
        console.print(f"    \u2192 {preferred} {reason}.")


def _get_lot_selection_data(
    ticker: str,
    qty: float,
    price: float,
    all_trades: list,
    lookback_triggers: list,
    etf_pairs: dict,
    today: date,
) -> tuple:
    """Compute lot selections and recommendation. Returns (selections_dict, recommendation) or (None, None)."""
    from net_alpha.engine.tax_position import (
        compute_tax_position,
        identify_open_lots,
        recommend_lot_method,
        select_lots,
    )

    open_lots = identify_open_lots(all_trades, as_of=today)

    ticker_lots = [lot for lot in open_lots if lot.ticker == ticker]
    if not ticker_lots:
        return (None, None)

    has_option_trades = any(t.is_option() and t.ticker == ticker for t in all_trades)
    if has_option_trades:
        console.print(f"\n  [dim]Note: {ticker} has option trades not shown in lot selection.[/dim]")

    total_available = sum(lot.quantity for lot in ticker_lots)
    if total_available < qty:
        console.print()
        console.print(f"  Only {int(total_available)} shares available across open lots for {ticker}.")
        return (None, None)

    selections = {}
    for method in ("FIFO", "HIFO", "LIFO"):
        sel = select_lots(open_lots, ticker, qty, method, price)
        if sel is not None:
            if sel.total_gain_loss < 0 and lookback_triggers:
                sel = sel.model_copy(update={"wash_sale_risk": True})
            selections[method] = sel

    if not selections:
        return (None, None)

    tp = compute_tax_position(all_trades, year=today.year)

    safe_sell_date = None
    if lookback_triggers:
        safe_sell_date = _compute_safe_date([t.date for t in lookback_triggers])

    rec = recommend_lot_method(selections, tp, safe_sell_date=safe_sell_date)

    return (selections, rec)


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
        cost_basis=1.0,
    )
