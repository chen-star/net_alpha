"""Data hygiene: surface trade/lot/cash data quality issues for triage."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from net_alpha.db.repository import Repository

HygieneCategory = Literal["unpriced", "basis_unknown", "orphan_sell", "dup_key"]
HygieneSeverity = Literal["info", "warn", "error"]


class HygieneFixForm(BaseModel):
    """An inline HTMX form rendered on a hygiene row."""

    action: str  # POST endpoint, e.g. /audit/set-basis
    fields: dict[str, str]  # field name -> field type ("date" | "number" | "text")
    hidden: dict[str, str]  # hidden form values, e.g. {"trade_id": "..."}


class HygieneIssue(BaseModel):
    category: HygieneCategory
    severity: HygieneSeverity
    summary: str
    detail: str
    fix_url: str | None = None
    fix_form: HygieneFixForm | None = None


def collect_issues(repo: Repository) -> list[HygieneIssue]:
    """Run all category checks against the current Repository state."""
    issues: list[HygieneIssue] = []
    issues.extend(_check_unpriced(repo))
    issues.extend(_check_basis_unknown(repo))
    issues.extend(_check_orphan_sells(repo))
    issues.extend(_check_dup_keys(repo))
    return issues


def _get_unpriced_symbols(repo: Repository) -> list[str]:
    """Symbols held in open lots without a cached price quote.

    Reads from the existing PriceCache. Only equity lots are checked (option
    lots don't drive the unpriced badge).
    """
    from net_alpha.pricing.cache import PriceCache

    engine = repo.engine
    cache = PriceCache(engine, ttl_seconds=86400)  # generous TTL — we just want presence
    symbols = sorted({lot.ticker for lot in repo.all_lots() if lot.option_details is None})
    missing: list[str] = []
    for s in symbols:
        if cache.get(s) is None:
            missing.append(s)
    return missing


def _check_unpriced(repo: Repository) -> list[HygieneIssue]:
    """Open lots whose ticker has no current price quote."""
    issues: list[HygieneIssue] = []
    for sym in _get_unpriced_symbols(repo):
        issues.append(
            HygieneIssue(
                category="unpriced",
                severity="warn",
                summary=f"{sym} has no price quote",
                detail=(
                    "Unrealized P&L for this symbol is excluded from totals. "
                    "Common causes: delisted, OTC, or symbol mismatch with Yahoo."
                ),
                fix_url=f"/holdings?symbol={sym}",
            )
        )
    return issues


def _check_basis_unknown(repo: Repository) -> list[HygieneIssue]:
    """Buy trades flagged ``basis_unknown=True`` (transfer-in without basis)."""
    issues: list[HygieneIssue] = []
    for t in repo.all_trades():
        if not t.basis_unknown:
            continue
        # Buy-side transfers in particular need basis to compute realized P&L
        # when sold. Sell-side basis_unknown is rarer (transfer_out) and
        # doesn't need user fix.
        if t.action.lower() != "buy":
            continue
        issues.append(
            HygieneIssue(
                category="basis_unknown",
                severity="error",
                summary=f"{t.ticker} buy on {t.date.isoformat()} has unknown basis",
                detail=(
                    f"Account: {t.account} · Qty: {t.quantity:.4f} · Source: {t.basis_source}. "
                    "Until basis is set, realized P&L for this lot can't be computed."
                ),
                fix_form=HygieneFixForm(
                    action="/audit/set-basis",
                    fields={"cost_basis": "number"},
                    hidden={"trade_id": t.id},
                ),
            )
        )
    return issues


def _check_orphan_sells(repo: Repository) -> list[HygieneIssue]:
    """A sell with no buy lot of the same ticker on/before its date.

    The wash-sale engine already tracks buy lots; if a Sell has no
    corresponding Lot row at all, the basis came from somewhere outside
    net-alpha's view (most often a missing prior-year import).
    """
    lots_by_ticker: dict[str, bool] = {}
    for lot in repo.all_lots():
        lots_by_ticker[lot.ticker] = True

    issues: list[HygieneIssue] = []
    for t in repo.all_trades():
        if t.action.lower() != "sell":
            continue
        if t.ticker in lots_by_ticker:
            continue
        issues.append(
            HygieneIssue(
                category="orphan_sell",
                severity="warn",
                summary=f"{t.ticker} sell on {t.date.isoformat()} has no matching buy lot",
                detail=(
                    "Usually means a missing prior-year import or a transfer not yet "
                    "hydrated. Realized P&L for this trade may be incorrect."
                ),
                fix_url="/imports",
            )
        )
    return issues


def _check_dup_keys(repo: Repository) -> list[HygieneIssue]:
    """Cluster of trades with the same natural-key signature on the same day.

    Same-day repeats with occurrence_index > 0 are normal — most parsers emit
    them when a single CSV row produces multiple Trades. But ≥3 trades sharing
    (date, account, ticker, action, quantity) is unusually dense and worth
    surfacing as info — could be a re-import that escaped dedup.
    """
    from collections import defaultdict

    clusters: dict[tuple, int] = defaultdict(int)
    for t in repo.all_trades():
        key = (t.date, t.account, t.ticker, t.action, round(t.quantity, 4))
        clusters[key] += 1

    issues: list[HygieneIssue] = []
    for (d, acct, ticker, action, qty), count in clusters.items():
        if count < 3:
            continue
        issues.append(
            HygieneIssue(
                category="dup_key",
                severity="info",
                summary=f"{count} {action} trades for {ticker} on {d.isoformat()}",
                detail=(
                    f"Account: {acct} · Qty per trade: {qty}. Same-day repeats are "
                    "usually normal but ≥3 occurrences suggests a possible re-import."
                ),
                fix_url="/imports",
            )
        )
    return issues
