from __future__ import annotations

from collections import defaultdict
from enum import StrEnum

from pydantic import BaseModel

from net_alpha.audit.brokers.registry import get_provider_for_account
from net_alpha.db.repository import Repository
from net_alpha.models.domain import Trade

DEFAULT_TOLERANCE = 0.50


class ReconciliationStatus(StrEnum):
    MATCH = "match"
    NEAR_MATCH = "near_match"  # within tolerance
    DIFF = "diff"  # exceeds tolerance
    UNAVAILABLE = "unavailable"  # no broker provider for this account


class ReconciliationResult(BaseModel):
    symbol: str
    account_id: int
    net_alpha_total: float
    broker_total: float | None
    delta: float
    status: ReconciliationStatus
    tolerance: float
    source_label: str | None  # e.g. "Schwab Realized G/L"


def reconcile(
    *,
    symbol: str,
    account_id: int,
    repo: Repository,
    tolerance: float = DEFAULT_TOLERANCE,
    tax_year: int | None = None,
) -> ReconciliationResult:
    """Reconcile net-alpha realized P&L against the broker's Realized G/L.

    By default (``tax_year=None``), both sides are summed over ALL time. This
    is correct only if the broker file covers the same lifetime scope as the
    user's net-alpha ledger. In practice users often upload only the current
    or prior tax year of G/L, so the lifetime totals diverge by exactly the
    P&L of the years the broker file omits — a misleading DIFF.

    Pass ``tax_year=<YYYY>`` (audit #15) to narrow both sides to closes whose
    ``closed_date.year == tax_year``. Web routes rendering a single-year period
    should thread the page-level year through this parameter.
    """
    provider = get_provider_for_account(account_id, repo)
    net_alpha_total = _net_alpha_realized(repo, account_id, symbol, tax_year=tax_year)

    if provider is None:
        return ReconciliationResult(
            symbol=symbol,
            account_id=account_id,
            net_alpha_total=net_alpha_total,
            broker_total=None,
            delta=0.0,
            status=ReconciliationStatus.UNAVAILABLE,
            tolerance=tolerance,
            source_label=None,
        )

    broker_lots = provider.get_lot_detail(account_id, symbol)
    if tax_year is not None:
        broker_lots = [
            lot for lot in broker_lots if getattr(lot, "closed", None) is not None
            and getattr(lot.closed, "year", None) == tax_year
        ]
    broker_total = sum((lot.proceeds or 0.0) - lot.cost_basis for lot in broker_lots)
    delta = round(net_alpha_total - broker_total, 4)
    if abs(delta) < 0.005:
        status = ReconciliationStatus.MATCH
    elif abs(delta) < tolerance:
        status = ReconciliationStatus.NEAR_MATCH
    else:
        status = ReconciliationStatus.DIFF

    source_label = broker_lots[0].source_label if broker_lots else None
    return ReconciliationResult(
        symbol=symbol,
        account_id=account_id,
        net_alpha_total=round(net_alpha_total, 2),
        broker_total=round(broker_total, 2),
        delta=delta,
        status=status,
        tolerance=tolerance,
        source_label=source_label,
    )


def reconcile_all(
    *,
    repo: Repository,
    tolerance: float = DEFAULT_TOLERANCE,
    tax_year: int | None = None,
) -> list[ReconciliationResult]:
    """Reconcile every (account, symbol) pair the repository knows about.

    Iterates `repo.list_accounts()` × the distinct tickers seen in
    `repo.get_gl_lots_for_account()` (i.e. only symbols where a broker
    Realized G/L row exists). Accounts without a broker provider yield
    UNAVAILABLE results, which downstream callers skip.

    Audit #15 follow-up: ``tax_year`` is forwarded to every per-symbol
    ``reconcile()`` call so callers can narrow both sides of the comparison
    to a single year. ``None`` (default) preserves the original
    lifetime-scope behaviour.

    Thin helper consumed by `verify/broker_recon.py::reconcile_realized_gl`
    — kept in `audit/` so module ownership stays with the reconciliation
    domain.
    """
    out: list[ReconciliationResult] = []
    for acct in repo.list_accounts():
        gl_lots = repo.get_gl_lots_for_account(acct.id)
        symbols = sorted({lot.symbol_raw for lot in gl_lots})
        for sym in symbols:
            out.append(
                reconcile(
                    symbol=sym,
                    account_id=acct.id,
                    repo=repo,
                    tolerance=tolerance,
                    tax_year=tax_year,
                )
            )
    return out


_OPTION_SHORT_CLOSE_SOURCES = {"option_short_close", "option_short_close_assigned"}


def _net_alpha_realized(
    repo: Repository,
    account_id: int,
    symbol: str,
    *,
    tax_year: int | None = None,
) -> float:
    """Sum realized P/L for the (account, symbol) pair.

    Includes:
      * Sell trades — standard equity/long-option close.
      * Buy-to-close (BTC) trades that close short options — these have
        ``action == "buy"`` with ``basis_source`` in the short-close set.
        For a BTC, ``(proceeds or 0) - (cost_basis or 0) == -cost_basis``,
        which correctly contributes the *expense* leg to a STO/BTC pair's
        net P&L. Excluding BTC left options-heavy accounts always DIFF
        against broker totals.

    Audit #15: when ``tax_year`` is provided, restrict to closes whose
    trade date falls in that calendar year so reconciliation against a
    single-year broker G/L file matches scopes.
    """
    total = 0.0
    accounts = {a.id: f"{a.broker}/{a.label}" if a.label else a.broker for a in repo.list_accounts()}
    target_display = accounts.get(account_id)
    for t in repo.get_trades_for_ticker(symbol):
        is_sell = t.action.lower() == "sell"
        is_short_close = t.action.lower() == "buy" and getattr(t, "basis_source", "") in _OPTION_SHORT_CLOSE_SOURCES
        if not (is_sell or is_short_close):
            continue
        if target_display is not None and t.account != target_display:
            continue
        if tax_year is not None and t.date.year != tax_year:
            continue
        total += (t.proceeds or 0.0) - (t.cost_basis or 0.0)
    return total


# ---------------------------------------------------------------------------
# Per-lot diff
# ---------------------------------------------------------------------------


class LotDiff(BaseModel):
    """One pair of (broker lot, net-alpha-derived realized) with a delta."""

    closed_date: object | None  # date | str
    opened_date: object | None
    qty: float
    broker_basis: float
    broker_proceeds: float | None
    net_alpha_basis: float | None
    net_alpha_proceeds: float | None
    delta: float
    likely_cause: str | None


def per_lot_diffs(
    *,
    symbol: str,
    account_id: int,
    repo: Repository,
) -> list[LotDiff]:
    """Pair broker G/L lots against net-alpha sell trades; return deltas with cause hints."""
    from datetime import date  # local import — avoids reshuffling top of file

    provider = get_provider_for_account(account_id, repo)
    if provider is None:
        return []
    broker_lots = provider.get_lot_detail(account_id, symbol)
    accounts = {a.id: f"{a.broker}/{a.label}" if a.label else a.broker for a in repo.list_accounts()}
    target_display = accounts.get(account_id)
    sells = [
        t
        for t in repo.get_trades_for_ticker(symbol)
        if t.action.lower() == "sell" and (target_display is None or t.account == target_display)
    ]
    # Multiple net-alpha sells can close on the same date (e.g. partial fills
    # of the same order, or two distinct orders the user submitted that day).
    # Group into per-date lists, then FIFO-consume each list as broker lots
    # are walked. Using a single-value dict here silently collapsed same-day
    # sells, producing simultaneous false-positive (broker has no match) and
    # false-negative (collapsed pair) findings.
    sells_by_date: dict[date, list[Trade]] = defaultdict(list)
    for t in sorted(sells, key=lambda x: x.date):
        sells_by_date[t.date].append(t)

    # Audit #34: per-sell consumption tracker. ``same_qty`` matches consume
    # a sell in one shot; the partial-fill path pro-rates the net-alpha sell
    # across the broker's HIFO split, tracking how much of the sell qty has
    # already been attributed to earlier broker lots in the same bucket.
    # Each sell stays in its bucket until cumulative broker qty for it >=
    # match.quantity (then removed).
    consumed_qty: dict[str, float] = defaultdict(float)

    diffs: list[LotDiff] = []
    for bl in broker_lots:
        if bl.closed is None:
            continue
        bucket = sells_by_date.get(bl.closed)
        if not bucket:
            diffs.append(
                LotDiff(
                    closed_date=bl.closed,
                    opened_date=bl.acquired,
                    qty=bl.qty,
                    broker_basis=bl.cost_basis,
                    broker_proceeds=bl.proceeds,
                    net_alpha_basis=None,
                    net_alpha_proceeds=None,
                    delta=0.0,
                    likely_cause="net-alpha has no matching sell on this date",
                )
            )
            continue
        # Prefer an exact same-qty match: consumes the sell in one shot.
        same_qty = next((t for t in bucket if abs((t.quantity or 0) - bl.qty) < 1e-6), None)
        if same_qty is not None:
            match = same_qty
            bucket.remove(match)
            na_basis = match.cost_basis or 0.0
            na_proceeds = match.proceeds or 0.0
        else:
            # Partial-fill: pro-rate the oldest unconsumed sell by bl.qty /
            # match.quantity so each broker LotDiff carries the matched
            # fraction of net-alpha proceeds + basis. Without this every
            # broker lot after the first was either orphaned or attributed
            # the FULL sell's basis/proceeds — both yielded wild deltas.
            match = bucket[0]
            full_qty = float(match.quantity or 0)
            full_basis = float(match.cost_basis or 0.0)
            full_proceeds = float(match.proceeds or 0.0)
            if full_qty > 0:
                fraction = bl.qty / full_qty
            else:
                fraction = 0.0
            na_basis = full_basis * fraction
            na_proceeds = full_proceeds * fraction
            consumed_qty[match.id] += bl.qty
            # Once cumulative consumption ≥ the sell's quantity, retire it
            # so subsequent broker lots on the same date attribute to the
            # next unconsumed sell (if any).
            if consumed_qty[match.id] >= full_qty - 1e-6:
                bucket.remove(match)

        delta = round(
            ((na_proceeds - na_basis) - ((bl.proceeds or 0.0) - bl.cost_basis)),
            4,
        )
        diffs.append(
            LotDiff(
                closed_date=bl.closed,
                opened_date=bl.acquired,
                qty=bl.qty,
                broker_basis=bl.cost_basis,
                broker_proceeds=bl.proceeds,
                net_alpha_basis=na_basis,
                net_alpha_proceeds=na_proceeds,
                delta=delta,
                likely_cause=_cause_hint(delta, bl, match),
            )
        )
    return diffs


def _cause_hint(delta: float, bl, na: Trade) -> str | None:
    """Lightweight heuristic — rendered as 'investigate' guidance."""
    if abs(delta) < 0.005:
        return None
    if bl.proceeds is not None and na.proceeds is not None:
        if abs((na.proceeds or 0) - (bl.proceeds or 0)) > abs((na.cost_basis or 0) - bl.cost_basis):
            return "proceeds mismatch — possible fee allocation difference"
    if bl.cost_basis != (na.cost_basis or 0.0):
        return "cost basis mismatch — possibly a wash-sale adjustment net-alpha applied differently"
    return "small numerical drift"
