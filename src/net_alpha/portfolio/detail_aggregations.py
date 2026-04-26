from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from net_alpha.models.domain import WashSaleViolation


@dataclass(frozen=True)
class DetailSummary:
    violation_count: int
    disallowed_total: Decimal
    confirmed_count: int
    probable_count: int
    unclear_count: int


@dataclass(frozen=True)
class TickerGroup:
    ticker: str
    violations: list[WashSaleViolation]
    violation_count: int
    disallowed_total: Decimal


def compute_detail_summary(violations: list[WashSaleViolation]) -> DetailSummary:
    total = Decimal("0")
    confirmed = probable = unclear = 0
    for v in violations:
        total += Decimal(str(v.disallowed_loss))
        c = v.confidence.lower()
        if c == "confirmed":
            confirmed += 1
        elif c == "probable":
            probable += 1
        elif c == "unclear":
            unclear += 1
    return DetailSummary(
        violation_count=len(violations),
        disallowed_total=total,
        confirmed_count=confirmed,
        probable_count=probable,
        unclear_count=unclear,
    )


def group_violations_by_ticker(violations: list[WashSaleViolation]) -> list[TickerGroup]:
    by_ticker: dict[str, list[WashSaleViolation]] = {}
    for v in violations:
        by_ticker.setdefault(v.ticker, []).append(v)

    groups = [
        TickerGroup(
            ticker=ticker,
            violations=vs,
            violation_count=len(vs),
            disallowed_total=sum((Decimal(str(v.disallowed_loss)) for v in vs), Decimal("0")),
        )
        for ticker, vs in by_ticker.items()
    ]
    groups.sort(key=lambda g: (-g.disallowed_total, g.ticker))
    return groups


def lag_days(v: WashSaleViolation) -> int | None:
    if v.loss_sale_date is None or v.triggering_buy_date is None:
        return None
    return (v.triggering_buy_date - v.loss_sale_date).days


def source_label(v: WashSaleViolation) -> str:
    if v.source == "schwab_g_l":
        return "Schwab"
    if v.loss_account and v.buy_account and v.loss_account != v.buy_account:
        return "Cross-account"
    return "Engine"
