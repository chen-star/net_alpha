"""Forward-looking wash-sale + §1091 watch over PositionTargets.

For each Position Target, simulate the trade implied by the target and
check for §1091 IRA-trap risk (a buy in a tax-advantaged account
within ±30 days of a taxable loss → permanent disallowance).

ETF-sibling matches are surfaced as 'soft' severity (the law is murky
for cross-broker ETF siblings); exact-ticker matches are 'hard'.

Ordinary cross-account wash-sale detection is currently a stub returning
clean — a future revision will wire engine.detector once the synthetic-
trade synthesis matures. The §1091 detection is the meaningful new
capability of v2.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from net_alpha.engine.etf_pairs import are_substantially_identical


@dataclass
class WatchResult:
    status: str  # 'clean' | 'wash_sale_risk' | 'ira_trap_risk' | 'cannot_evaluate'
    severity: str = "none"  # 'none' | 'soft' | 'hard'
    reason: str | None = None
    triggering_trade_ids: list[int] | None = None


def evaluate_target(*, target: Any, repo: Any, today: date) -> WatchResult:
    """Evaluate a PositionTarget for forward-looking wash-sale / §1091 risk.

    Args:
        target: A PositionTarget (or mock with .symbol, .broker, .account,
                .target_shares / .target_dollars attributes).
        repo:   A Repository (or mock) with:
                  - latest_price(symbol) -> Decimal | None
                  - position_quantity(ticker, broker, account) -> Decimal
                  - average_basis(ticker, broker, account) -> Decimal | None
                  - get_account_type(broker, label) -> str
                  - buys_in_window_non_taxable(start, end) -> list
        today:  The reference date for window calculations.

    Returns:
        WatchResult with status/severity/reason/triggering_trade_ids.
    """
    price = repo.latest_price(target.symbol)
    if price is None:
        return WatchResult(status="cannot_evaluate", severity="none", reason="no price quote")

    broker = getattr(target, "broker", None)
    held = repo.position_quantity(ticker=target.symbol, broker=broker, account=target.account)
    desired = _desired_shares(target, price)

    delta = Decimal(str(desired)) - Decimal(str(held))

    # Only sells (delta < 0) can trigger wash-sale / §1091. If delta >= 0, nothing to check.
    if delta >= 0:
        return WatchResult(status="clean", severity="none")

    # Is the close a loss-realizer?
    avg_basis = repo.average_basis(ticker=target.symbol, broker=broker, account=target.account)
    if avg_basis is None or Decimal(str(price)) >= Decimal(str(avg_basis)):
        return WatchResult(status="clean", severity="none")

    # §1091 check: only relevant for taxable account closes.
    account_type = repo.get_account_type(broker=broker, label=target.account)
    if account_type != "taxable":
        return WatchResult(status="clean", severity="none")

    window_start = today - timedelta(days=30)
    window_end = today + timedelta(days=30)
    candidates = repo.buys_in_window_non_taxable(start=window_start, end=window_end)

    matches: list = []
    has_exact = False
    for c in candidates:
        if c.ticker == target.symbol:
            has_exact = True
            matches.append(c)
        elif are_substantially_identical(c.ticker, target.symbol):
            matches.append(c)

    if not matches:
        # No §1091 risk detected. Ordinary wash-sale detection (same-taxable-account
        # buys within ±30 days) is deferred to a future revision once synthetic-trade
        # synthesis matures; report clean for now.
        return WatchResult(status="clean", severity="none")

    severity = "hard" if has_exact else "soft"
    first = matches[0]
    return WatchResult(
        status="ira_trap_risk",
        severity=severity,
        reason=(f"Buy in {first.account} on {first.trade_date} would permanently disallow this loss (§1091)."),
        triggering_trade_ids=[m.id for m in matches],
    )


def _desired_shares(target: Any, price: Decimal) -> Decimal:
    """Resolve target to a share quantity.

    Checks target_shares first, then target_dollars (converted at price),
    defaulting to zero if neither is set.
    """
    target_shares = getattr(target, "target_shares", None)
    if target_shares is not None:
        return Decimal(str(target_shares))
    target_dollars = getattr(target, "target_dollars", None)
    if target_dollars is not None:
        return (Decimal(str(target_dollars)) / Decimal(str(price))).quantize(Decimal("0.0001"))
    return Decimal("0")
