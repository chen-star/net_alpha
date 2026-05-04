"""Plan tab view-model: combine targets + current holdings + quotes into rows."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from net_alpha.portfolio.models import PositionRow
from net_alpha.targets.models import PositionTarget, TargetUnit


_UNTAGGED = "untagged"


@dataclass(frozen=True)
class PlanRow:
    symbol: str
    target_unit: TargetUnit
    target_amount: Decimal
    target_dollar_equiv: Decimal | None
    target_share_equiv: Decimal | None
    current_dollar: Decimal
    current_shares: Decimal
    gap_dollar: Decimal
    gap_shares: Decimal | None
    pct_filled: Decimal | None
    last_price: Decimal | None
    is_held: bool
    tags: tuple[str, ...] = field(default=())


@dataclass(frozen=True)
class PlanTagSummary:
    tag: str
    target_count: int
    planned_dollar: Decimal | None
    current_dollar: Decimal
    gap_to_fill_dollar: Decimal
    pct_filled: Decimal | None


@dataclass(frozen=True)
class PlanView:
    rows: list[PlanRow]
    total_to_fill_dollar: Decimal
    free_cash: Decimal
    coverage_pct: Decimal | None
    total_planned_dollar: Decimal
    planned_rows_with_quote: int
    planned_rows_total: int
    tag_summaries: list[PlanTagSummary] = field(default_factory=list)
    all_tags: tuple[str, ...] = field(default=())
    selected_tag: str | None = None
    sort_key: str = "alpha"


_TWO = Decimal("0.01")


def _quantize(d: Decimal | None) -> Decimal | None:
    if d is None:
        return None
    return d.quantize(_TWO)


def _build_tag_summaries(rows: list[PlanRow]) -> list[PlanTagSummary]:
    """Aggregate per-tag stats. A row with N tags counts in N buckets.
    Rows with no tags fall into the synthetic 'untagged' bucket."""
    by_tag: dict[str, list[PlanRow]] = {}
    for r in rows:
        keys = r.tags if r.tags else (_UNTAGGED,)
        for k in keys:
            by_tag.setdefault(k, []).append(r)

    summaries: list[PlanTagSummary] = []
    for tag in sorted(by_tag.keys(), key=lambda k: (k == _UNTAGGED, k)):
        bucket = by_tag[tag]
        current = sum((r.current_dollar for r in bucket), Decimal("0"))
        gap = sum(
            (r.gap_dollar for r in bucket if r.gap_dollar > Decimal("0")),
            Decimal("0"),
        )
        if any(r.target_dollar_equiv is None for r in bucket):
            planned: Decimal | None = None
        else:
            planned = sum(
                (r.target_dollar_equiv for r in bucket),
                Decimal("0"),
            ).quantize(_TWO)
        if planned is None or planned == Decimal("0"):
            pct: Decimal | None = None
        else:
            pct = (current / planned * Decimal("100")).quantize(_TWO)
        summaries.append(
            PlanTagSummary(
                tag=tag,
                target_count=len(bucket),
                planned_dollar=planned,
                current_dollar=current.quantize(_TWO),
                gap_to_fill_dollar=gap.quantize(_TWO),
                pct_filled=pct,
            )
        )
    return summaries


def build_plan_view(
    *,
    targets: list[PositionTarget],
    positions_by_symbol: dict[str, PositionRow],
    quotes_by_symbol: dict[str, Decimal],
    free_cash: Decimal,
) -> PlanView:
    rows: list[PlanRow] = []
    for t in sorted(targets, key=lambda x: x.symbol):
        last_price = quotes_by_symbol.get(t.symbol)
        pos = positions_by_symbol.get(t.symbol)
        current_dollar = pos.market_value if (pos and pos.market_value is not None) else Decimal("0")
        current_shares = pos.qty if pos else Decimal("0")

        # Compute target equivalents in both units when possible.
        if t.target_unit == TargetUnit.USD:
            target_dollar_equiv = t.target_amount
            if last_price and last_price != 0:
                target_share_equiv = (t.target_amount / last_price).quantize(_TWO)
            else:
                target_share_equiv = None
        else:
            target_share_equiv = t.target_amount
            if last_price and last_price != 0:
                target_dollar_equiv = (t.target_amount * last_price).quantize(_TWO)
            else:
                target_dollar_equiv = None

        # Gaps. Dollar gap is always present when target_dollar_equiv is.
        if target_dollar_equiv is not None:
            gap_dollar = target_dollar_equiv - current_dollar
        else:
            gap_dollar = Decimal("0")  # cannot compute without quote

        if target_share_equiv is not None:
            gap_shares = target_share_equiv - current_shares
        else:
            gap_shares = None

        # % filled is computed in the user's chosen unit.
        pct_filled: Decimal | None
        if t.target_unit == TargetUnit.USD and t.target_amount != 0:
            pct_filled = (current_dollar / t.target_amount * Decimal("100")).quantize(_TWO)
        elif t.target_unit == TargetUnit.SHARES and t.target_amount != 0:
            pct_filled = (current_shares / t.target_amount * Decimal("100")).quantize(_TWO)
        else:
            pct_filled = None

        rows.append(
            PlanRow(
                symbol=t.symbol,
                target_unit=t.target_unit,
                target_amount=t.target_amount,
                target_dollar_equiv=_quantize(target_dollar_equiv),
                target_share_equiv=target_share_equiv,
                current_dollar=current_dollar.quantize(_TWO),
                current_shares=current_shares,
                gap_dollar=gap_dollar.quantize(_TWO),
                gap_shares=gap_shares,
                pct_filled=pct_filled,
                last_price=last_price,
                is_held=pos is not None,
                tags=t.tags,
            )
        )

    total_to_fill = sum(
        (r.gap_dollar for r in rows if r.gap_dollar > Decimal("0")),
        Decimal("0"),
    )
    if total_to_fill > Decimal("0"):
        coverage_pct = (free_cash / total_to_fill * Decimal("100")).quantize(_TWO)
    else:
        coverage_pct = None

    total_planned = sum(
        (r.target_dollar_equiv for r in rows if r.target_dollar_equiv is not None),
        Decimal("0"),
    )
    planned_with_quote = sum(1 for r in rows if r.target_dollar_equiv is not None)

    tag_summaries = _build_tag_summaries(rows)
    all_tags = tuple(sorted({tag for r in rows for tag in r.tags}))

    return PlanView(
        rows=rows,
        total_to_fill_dollar=total_to_fill,
        free_cash=free_cash,
        coverage_pct=coverage_pct,
        total_planned_dollar=total_planned.quantize(_TWO),
        planned_rows_with_quote=planned_with_quote,
        planned_rows_total=len(rows),
        tag_summaries=tag_summaries,
        all_tags=all_tags,
        selected_tag=None,
        sort_key="alpha",
    )
