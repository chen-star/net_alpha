from __future__ import annotations

from dataclasses import dataclass, field

from net_alpha.db.repository import Repository
from net_alpha.models.domain import Trade

_QUANTITY_TOLERANCE = 0.005  # 0.5% allowed delta between G/L sum and sell qty


@dataclass
class StitchOutcome:
    """Result for one Sell trade."""

    source: str  # "g_l" | "fifo" | "unknown"
    warning: str | None = None


@dataclass
class StitchSummary:
    """Aggregated counts across all sells in an account."""

    from_gl: int = 0
    from_fifo: int = 0
    unknown: int = 0
    warnings: list[str] = field(default_factory=list)

    def add(self, outcome: StitchOutcome) -> None:
        if outcome.source == "g_l":
            self.from_gl += 1
        elif outcome.source == "fifo":
            self.from_fifo += 1
        else:
            self.unknown += 1
        if outcome.warning:
            self.warnings.append(outcome.warning)


def match_symbol(t: Trade) -> str:
    """Reconstruct the comparable raw symbol from a Trade for G/L matching.

    Stocks: just the ticker.
    Options: 'TICKER MM/DD/YYYY STRIKE.XX C|P' (Schwab format).
    """
    if t.option_details is not None:
        opt = t.option_details
        expiry = opt.expiry.strftime("%m/%d/%Y")
        return f"{t.ticker} {expiry} {opt.strike:.2f} {opt.call_put}"
    return t.ticker


def _try_gl(repo: Repository, sell: Trade, account_id: int) -> StitchOutcome | None:
    gl_rows = repo.get_gl_lots_for_match(
        account_id=account_id,
        symbol_raw=match_symbol(sell),
        closed_date=sell.date,
    )
    if not gl_rows:
        return None
    agg_qty = sum(r.quantity for r in gl_rows)
    agg_cb = sum(r.cost_basis for r in gl_rows)
    warning = None
    if sell.quantity > 0 and abs(agg_qty - sell.quantity) / sell.quantity > _QUANTITY_TOLERANCE:
        warning = (
            f"{match_symbol(sell)} on {sell.date.isoformat()}: "
            f"G/L lot quantities ({agg_qty:.4f}) don't sum to sell quantity ({sell.quantity:.4f})"
        )
    repo.update_trade_basis(sell.id, cost_basis=agg_cb, basis_source="g_l")
    return StitchOutcome(source="g_l", warning=warning)


def _try_fifo(repo: Repository, sell: Trade, account_id: int) -> StitchOutcome | None:
    buys = repo.get_buys_before_date(account_id=account_id, ticker=sell.ticker, before_date=sell.date)
    if not buys:
        return None
    needed = sell.quantity
    consumed_qty = 0.0
    consumed_basis = 0.0
    for b in buys:
        take = min(b.quantity, needed - consumed_qty)
        if take <= 0:
            break
        per_unit = (b.cost_basis or 0.0) / b.quantity if b.quantity > 0 else 0.0
        consumed_qty += take
        consumed_basis += take * per_unit
        if consumed_qty >= needed * (1 - _QUANTITY_TOLERANCE):
            break
    if consumed_qty < needed * (1 - _QUANTITY_TOLERANCE):
        return None  # Not enough buys to cover
    repo.update_trade_basis(sell.id, cost_basis=consumed_basis, basis_source="fifo")
    return StitchOutcome(source="fifo")


def stitch_account(repo: Repository, account_id: int) -> StitchSummary:
    """Hydrate cost_basis on every Sell trade in the account.

    For each Sell:
      1. Try G/L match (preferred).
      2. Fall back to FIFO consumption of buy lots.
      3. Otherwise mark basis_source='unknown' and leave cost_basis NULL.
    """
    summary = StitchSummary()
    for sell in repo.get_sells_for_account(account_id):
        outcome = _try_gl(repo, sell, account_id)
        if outcome is None:
            outcome = _try_fifo(repo, sell, account_id)
        if outcome is None:
            repo.update_trade_basis(sell.id, cost_basis=None, basis_source="unknown")
            outcome = StitchOutcome(source="unknown")
        summary.add(outcome)
    return summary
