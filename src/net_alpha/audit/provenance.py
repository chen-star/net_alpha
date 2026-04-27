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
    action: str       # "Buy" | "Sell"
    quantity: float
    amount: float     # signed: positive for proceeds, negative for cost
    symbol: str
    import_id: int | None


class AppliedAdjustment(BaseModel):
    """A wash-sale basis transfer applied to one of the contributing trades."""

    violation_id: str
    loss_trade_id: str
    replacement_trade_id: str
    rolled_amount: float          # disallowed loss rolled into replacement basis
    confidence: str               # "Confirmed" | "Probable" | "Unclear"
    rule_citation: str = "IRS Pub 550 §1091 — 30-day window"


class ContributingCashEvent(BaseModel):
    event_id: str
    event_date: date
    account: str
    kind: str                      # transfer_in | transfer_out | dividend | interest | fee | sweep_in | sweep_out
    amount: float                  # signed
    description: str = ""


class ProvenanceTrace(BaseModel):
    """The complete 'why is this number what it is' record for one MetricRef."""

    metric_label: str              # human-readable, e.g. "YTD 2026 Realized P/L · AAPL"
    total: float                   # the number the user sees on the page
    trades: list[ContributingTrade] = Field(default_factory=list)
    adjustments: list[AppliedAdjustment] = Field(default_factory=list)
    cash_events: list[ContributingCashEvent] = Field(default_factory=list)
