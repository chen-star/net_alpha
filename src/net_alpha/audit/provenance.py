"""Provenance: 'why is this number what it is?' for every KPI in the app.

`MetricRef` is a discriminated Pydantic union; one variant per drillable metric
type. `provenance_for(metric_ref, repo)` returns a `ProvenanceTrace` containing
the trades, wash-sale adjustments, and cash events that produced the number.
The trace is rendered as an HTMX modal fragment.
"""

from __future__ import annotations

import base64
import json
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from net_alpha.db.repository import Repository
from net_alpha.models.domain import Trade


class Period(BaseModel):
    """A date window for KPI scoping. ``end`` is exclusive."""

    start: date
    end: date
    label: str  # e.g. "YTD 2026", "Lifetime", "2025"


class RealizedPLRef(BaseModel):
    kind: Literal["realized_pl"]
    period: Period
    account_id: int | None  # None = aggregate across accounts
    symbol: str | None  # None = aggregate across symbols


class UnrealizedPLRef(BaseModel):
    kind: Literal["unrealized_pl"]
    account_id: int | None
    symbol: str | None


class WashImpactRef(BaseModel):
    kind: Literal["wash_impact"]
    period: Period
    account_id: int | None


class CashRef(BaseModel):
    kind: Literal["cash"]
    account_id: int | None


class NetContributedRef(BaseModel):
    kind: Literal["net_contributed"]
    period: Period
    account_id: int | None


MetricRef = Annotated[
    RealizedPLRef | UnrealizedPLRef | WashImpactRef | CashRef | NetContributedRef,
    Field(discriminator="kind"),
]

_metric_ref_adapter: TypeAdapter[MetricRef] = TypeAdapter(MetricRef)


def encode_metric_ref(ref: MetricRef) -> str:
    """Serialize a MetricRef to a URL-safe base64 string for the route path."""
    payload = _metric_ref_adapter.dump_json(ref).decode("utf-8")
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")


def decode_metric_ref(encoded: str) -> MetricRef:
    """Inverse of encode_metric_ref. Raises ValueError on invalid input."""
    try:
        padded = encoded + "=" * (-len(encoded) % 4)
        payload = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        data = json.loads(payload)
        return _metric_ref_adapter.validate_python(data)
    except (ValueError, ValidationError, UnicodeDecodeError) as e:
        raise ValueError(f"invalid metric ref: {e}") from e


class ContributingTrade(BaseModel):
    trade_id: str
    trade_date: date
    account: str
    action: str  # "Buy" | "Sell"
    quantity: float
    amount: float  # signed: positive for proceeds, negative for cost
    symbol: str
    import_id: int | None


class AppliedAdjustment(BaseModel):
    """A wash-sale basis transfer applied to one of the contributing trades."""

    violation_id: str
    loss_trade_id: str
    replacement_trade_id: str
    rolled_amount: float  # disallowed loss rolled into replacement basis
    confidence: str  # "Confirmed" | "Probable" | "Unclear"
    rule_citation: str = "IRS Pub 550 §1091 — 30-day window"


class ContributingCashEvent(BaseModel):
    event_id: str
    event_date: date
    account: str
    kind: str  # transfer_in | transfer_out | dividend | interest | fee | sweep_in | sweep_out
    amount: float  # signed
    description: str = ""


class ProvenanceTrace(BaseModel):
    """The complete 'why is this number what it is' record for one MetricRef."""

    metric_label: str  # human-readable, e.g. "YTD 2026 Realized P/L · AAPL"
    total: float  # the number the user sees on the page
    trades: list[ContributingTrade] = Field(default_factory=list)
    adjustments: list[AppliedAdjustment] = Field(default_factory=list)
    cash_events: list[ContributingCashEvent] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Dispatcher — extend by adding elif isinstance(metric, XxxRef) branches
# ---------------------------------------------------------------------------


def provenance_for(metric: MetricRef, repo: Repository) -> ProvenanceTrace:
    """Return the trades / adjustments / cash events that produced ``metric``.

    Dispatches on the discriminator field. Raises ``KeyError`` if a new
    MetricRef variant is added without a matching dispatch — caller surfaces
    this as the modal's failure block.
    """
    if isinstance(metric, RealizedPLRef):
        return _realized_pl(metric, repo)
    if isinstance(metric, UnrealizedPLRef):
        return _unrealized_pl(metric, repo)
    if isinstance(metric, WashImpactRef):
        return _wash_impact(metric, repo)
    if isinstance(metric, CashRef):
        return _cash(metric, repo)
    if isinstance(metric, NetContributedRef):
        return _net_contributed(metric, repo)
    raise KeyError(f"no provenance dispatcher for {metric.kind!r}")


def _trade_in_period(t: Trade, period: Period) -> bool:
    return period.start <= t.date < period.end


def _accounts_by_id(repo: Repository) -> dict[int, str]:
    """Build a one-shot id → display map; callers iterate without re-querying."""
    return {a.id: f"{a.broker}/{a.label}" if a.label else a.broker for a in repo.list_accounts()}


def _to_contributing(t: Trade, import_id: int | None) -> ContributingTrade:
    amount = (t.proceeds or 0.0) if t.action.lower() == "sell" else -(t.cost_basis or 0.0)
    return ContributingTrade(
        trade_id=t.id,
        trade_date=t.date,
        account=t.account,
        action=t.action,
        quantity=t.quantity,
        amount=amount,
        symbol=t.ticker,
        import_id=import_id,
    )


def _realized_pl(metric: RealizedPLRef, repo: Repository) -> ProvenanceTrace:
    """Provenance trace for realized P&L.

    Iterates the same Sell rows the user sees, but the displayed `total` uses
    the canonical realized helper so STO/BTC option pairing is honored. The
    contributing-trades list still surfaces every Sell that touched the
    metric scope so the user can audit raw inputs; only the headline number
    reflects the corrected math.
    """
    contributing: list[ContributingTrade] = []
    accounts = _accounts_by_id(repo)
    target_display = accounts.get(metric.account_id) if metric.account_id is not None else None
    scoped: list[Trade] = []
    for t in repo.all_trades():
        if metric.symbol is not None and t.ticker != metric.symbol:
            continue
        if target_display is not None and t.account != target_display:
            continue
        scoped.append(t)
        if t.action.lower() != "sell":
            continue
        if not _trade_in_period(t, metric.period):
            continue
        contributing.append(_to_contributing(t, import_id=None))

    from net_alpha.portfolio.pnl import realized_pl_from_trades

    # Period.end is exclusive; pnl helper expects (year_start, year_end_excl).
    # When end > Dec 31 of start.year (e.g. Lifetime spanning multi-year), the
    # helper period filter is permissive enough — we only need the year bounds.
    period_tuple = (metric.period.start.year, metric.period.end.year + 1)
    if metric.period.end.year - metric.period.start.year > 50:
        period_tuple = None  # treat very-wide windows ("Lifetime") as no filter
    # Pull GL lots for the same scope so synthesized expirations land in the
    # provenance total (matches what the user sees on the Portfolio/Ticker pages).
    gl_lots_scoped = repo.list_all_gl_lots()
    if metric.symbol is not None:
        gl_lots_scoped = [g for g in gl_lots_scoped if g.ticker == metric.symbol]
    if target_display is not None:
        gl_lots_scoped = [g for g in gl_lots_scoped if g.account_display == target_display]
    total = float(realized_pl_from_trades(scoped, period=period_tuple, gl_lots=gl_lots_scoped))

    label_bits = [metric.period.label, "Realized P/L"]
    if metric.symbol:
        label_bits.append(f"· {metric.symbol}")
    return ProvenanceTrace(
        metric_label=" ".join(label_bits),
        total=round(total, 2),
        trades=contributing,
    )


def _unrealized_pl(metric: UnrealizedPLRef, repo: Repository) -> ProvenanceTrace:
    """Open lots' contributing buys (cost basis side of unrealized math).

    Note: unrealized P/L = market_value − adjusted_basis. This trace surfaces
    the adjusted_basis component (the trades) — the price/market component is
    a single "today" quote and isn't a 'trade' to provenance against.
    """
    contributing: list[ContributingTrade] = []
    total = 0.0
    trade_by_id = {t.id: t for t in repo.all_trades()}  # hoisted lookup
    accounts = _accounts_by_id(repo)
    target_display = accounts.get(metric.account_id) if metric.account_id is not None else None
    for lot in repo.all_lots():
        if metric.symbol is not None and lot.ticker != metric.symbol:
            continue
        if target_display is not None and lot.account != target_display:
            continue
        # The lot was created by the buy trade with id == lot.trade_id.
        buy = trade_by_id.get(lot.trade_id)
        if buy is None:
            continue
        contributing.append(
            ContributingTrade(
                trade_id=buy.id,
                trade_date=buy.date,
                account=buy.account,
                action="Buy",
                quantity=lot.quantity,
                amount=-lot.adjusted_basis,
                symbol=lot.ticker,
                import_id=None,
            )
        )
        total -= lot.adjusted_basis

    label_bits = ["Unrealized P/L"]
    if metric.symbol:
        label_bits.append(f"· {metric.symbol}")
    return ProvenanceTrace(
        metric_label=" ".join(label_bits),
        total=round(total, 2),
        trades=contributing,
    )


_TRANSFER_KINDS = frozenset({"transfer_in", "transfer_out"})
# Sweeps move money between Schwab1 brokerage and the Schwab Futures
# sub-account; they're cash-neutral at the combined-account level (see
# portfolio/cash_flow.py) and so are excluded from cash provenance too —
# otherwise the per-event totals would not reconcile to the displayed
# cash balance.
_SWEEP_KINDS = frozenset({"sweep_in", "sweep_out"})


def _to_contributing_cash(ev) -> ContributingCashEvent:
    sign = -1.0 if ev.kind in {"transfer_out", "fee"} else 1.0
    return ContributingCashEvent(
        event_id=ev.id,
        event_date=ev.event_date,
        account=ev.account,
        kind=ev.kind,
        amount=sign * ev.amount,
        description=ev.description,
    )


def _cash(metric: CashRef, repo: Repository) -> ProvenanceTrace:
    events = []
    total = 0.0
    for ev in repo.list_cash_events(account_id=metric.account_id):
        if ev.kind in _SWEEP_KINDS:
            continue
        contrib = _to_contributing_cash(ev)
        events.append(contrib)
        total += contrib.amount
    return ProvenanceTrace(
        metric_label="Cash balance",
        total=round(total, 2),
        cash_events=events,
    )


def _net_contributed(metric: NetContributedRef, repo: Repository) -> ProvenanceTrace:
    events = []
    total = 0.0
    for ev in repo.list_cash_events(account_id=metric.account_id):
        if ev.kind not in _TRANSFER_KINDS:
            continue
        if not (metric.period.start <= ev.event_date < metric.period.end):
            continue
        contrib = _to_contributing_cash(ev)
        events.append(contrib)
        total += contrib.amount
    return ProvenanceTrace(
        metric_label=f"{metric.period.label} Net Contributed",
        total=round(total, 2),
        cash_events=events,
    )


def _wash_impact(metric: WashImpactRef, repo: Repository) -> ProvenanceTrace:
    accounts = _accounts_by_id(repo)
    scoped_display = accounts.get(metric.account_id) if metric.account_id is not None else None
    adjustments: list[AppliedAdjustment] = []
    total = 0.0
    for v in repo.all_violations():
        if v.loss_sale_date is None or not (metric.period.start <= v.loss_sale_date < metric.period.end):
            continue
        if scoped_display is not None and scoped_display not in (v.loss_account, v.buy_account):
            continue
        total += v.disallowed_loss
        adjustments.append(
            AppliedAdjustment(
                violation_id=v.id,
                loss_trade_id=v.loss_trade_id,
                replacement_trade_id=v.replacement_trade_id,
                rolled_amount=v.disallowed_loss,
                confidence=v.confidence,
            )
        )
    return ProvenanceTrace(
        metric_label=f"{metric.period.label} Wash Impact",
        total=round(total, 2),
        adjustments=adjustments,
    )
