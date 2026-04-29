"""Data hygiene: surface trade/lot/cash data quality issues for triage."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Literal

from pydantic import BaseModel

from net_alpha.config import Settings, load_tax_config
from net_alpha.db.repository import Repository

# Schwab appends a numeric suffix to an option's underlying after a corporate
# action ("GME" → "GME1"). The original BTO and the matching STC may carry
# different tickers in the trade table — economically the same position. Strip
# trailing digits when matching option events so the pair nets out. (Same
# pattern used in net_alpha.portfolio.positions._opt_ticker_base.)
_OPT_CORP_ACTION_SUFFIX = re.compile(r"\d+$")


def _opt_ticker_base(ticker: str) -> str:
    return _OPT_CORP_ACTION_SUFFIX.sub("", ticker)


HygieneCategory = Literal["unpriced", "basis_unknown", "orphan_sell", "dup_key", "tax_config_missing"]
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


class MissingBasisRow(BaseModel):
    """Lightweight row for the Imports drawer inline-form (§6.2 I1/I2).

    Carries only the fields the ``_data_hygiene_row.html`` template needs:
    ``trade_id``, ``symbol``, ``qty``, ``acquired_date``.
    """

    trade_id: int
    symbol: str
    qty: float
    acquired_date: object  # datetime.date — kept as `object` to avoid circular imports


def collect_missing_basis_rows(repo: Repository) -> list[MissingBasisRow]:
    """Return one row per buy trade flagged ``basis_unknown=True``.

    Used by the Imports drawer to render a single explanation card + one
    compact inline form per row (§6.2 I1/I2).
    """
    rows: list[MissingBasisRow] = []
    for t in repo.all_trades():
        if not t.basis_unknown:
            continue
        if t.action.lower() != "buy":
            continue
        if t.id is None:
            continue
        rows.append(
            MissingBasisRow(
                trade_id=t.id,
                symbol=t.ticker,
                qty=t.quantity,
                acquired_date=t.date,
            )
        )
    return rows


def collect_issues(repo: Repository, settings: Settings | None = None) -> list[HygieneIssue]:
    """Run all category checks against the current Repository state."""
    issues: list[HygieneIssue] = []
    issues.extend(_check_unpriced(repo))
    issues.extend(_check_basis_unknown(repo))
    issues.extend(_check_orphan_sells(repo))
    issues.extend(_check_dup_keys(repo))
    if settings is not None:
        issues.extend(_check_tax_config_missing(settings))
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
    """Open lots whose ticker has no current price quote.

    Informational only: there's no in-app action to fix a missing Yahoo quote
    (it's environmental — delisted, OTC, or symbol mismatch). We surface it
    so the user understands why the symbol's market value reads as zero.
    """
    issues: list[HygieneIssue] = []
    for sym in _get_unpriced_symbols(repo):
        issues.append(
            HygieneIssue(
                category="unpriced",
                severity="info",
                summary=f"{sym} has no price quote",
                detail=(
                    "Yahoo Finance returned no quote for this symbol, so its market "
                    "value is excluded from Portfolio totals. Common causes: "
                    "delisted, OTC, or symbol mismatch (Yahoo uses a different "
                    "ticker — e.g. BRK.B vs BRK-B). Lot-level cost basis and "
                    "realized P&L are unaffected; this only impacts the "
                    "Portfolio market-value KPI."
                ),
            )
        )
    return issues


def _check_basis_unknown(repo: Repository) -> list[HygieneIssue]:
    """Buy trades flagged ``basis_unknown=True`` (transfer-in without basis).

    Link out to the ticker detail page where the basis editor lives — the same
    "set basis & date" affordance the timeline already shows for transfer rows.
    Keeping a single edit point avoids the two-place-edit confusion.
    """
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
                    "Until basis is set, realized P&L for this lot can't be computed. "
                    "Edit it on the ticker detail page (the timeline 'set basis & date' link)."
                ),
                fix_url=f"/ticker/{t.ticker}#trade-affordance-{t.id}",
            )
        )
    return issues


def _check_orphan_sells(repo: Repository) -> list[HygieneIssue]:
    """A sell with no buy lot of the same ticker on/before its date.

    The wash-sale engine already tracks buy lots; if a Sell has no
    corresponding Lot row at all, the basis came from somewhere outside
    net-alpha's view (most often a missing prior-year import).

    Excludes option sell-to-open trades (basis_source == "option_short_open*"):
    those create the position rather than close one, so a missing buy lot is
    by design — the matching close (BTC / expiry / assignment) comes later.

    For option closes, matches on the digit-stripped ticker base so that a
    Schwab corp-action rename (e.g. GME → GME1 BTO followed by STC under
    GME1) doesn't get falsely flagged.
    """
    eq_lot_tickers: set[str] = set()
    opt_lot_keys: set[tuple[str, float, object, str]] = set()
    for lot in repo.all_lots():
        if lot.option_details is None:
            eq_lot_tickers.add(lot.ticker)
        else:
            opt = lot.option_details
            opt_lot_keys.add((_opt_ticker_base(lot.ticker), opt.strike, opt.expiry, opt.call_put))

    issues: list[HygieneIssue] = []
    for t in repo.all_trades():
        if t.action.lower() != "sell":
            continue
        # Sell-to-open of an option is not an orphan — it opens a short.
        if t.basis_source.startswith("option_short_open"):
            continue
        if t.option_details is not None:
            opt = t.option_details
            key = (_opt_ticker_base(t.ticker), opt.strike, opt.expiry, opt.call_put)
            if key in opt_lot_keys:
                continue
        else:
            if t.ticker in eq_lot_tickers:
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
    """Cluster of trades that look like a re-import duplicate, not averaging-down.

    Trades sharing (date, account, ticker, action, quantity, price-per-share)
    are very likely a re-import that escaped dedup. Same date+ticker+action with
    *different* prices (averaging down/up) is normal trading — we don't warn.
    """

    def _price_key(t) -> str:
        # Use rounded price per share so true duplicates collide while
        # different-price legs (averaging) stay separate.
        if t.quantity == 0:
            return ""
        amt = t.cost_basis if t.action.lower() == "buy" else t.proceeds
        if amt is None:
            return ""
        return f"{round(amt / t.quantity, 4)}"

    clusters: dict[tuple, int] = defaultdict(int)
    for t in repo.all_trades():
        key = (t.date, t.account, t.ticker, t.action, round(t.quantity, 4), _price_key(t))
        clusters[key] += 1

    issues: list[HygieneIssue] = []
    for (d, acct, ticker, action, qty, _ppk), count in clusters.items():
        if count < 3:
            continue
        issues.append(
            HygieneIssue(
                category="dup_key",
                severity="info",
                summary=f"{count} identical {action} trades for {ticker} on {d.isoformat()}",
                detail=(
                    f"Account: {acct} · Qty per trade: {qty}. Same-day repeats at the same "
                    "price (≥3) usually indicate a re-import that escaped dedup. "
                    "Different prices on the same day are normal averaging and aren't flagged."
                ),
                fix_url="/imports",
            )
        )
    return issues


def _check_tax_config_missing(settings: Settings) -> list[HygieneIssue]:
    if load_tax_config(settings.config_yaml_path) is not None:
        return []
    return [
        HygieneIssue(
            category="tax_config_missing",
            severity="info",
            summary="Tax bracket configuration not set",
            detail=(
                "The year-end tax projection on the Tax page is disabled until "
                "you fill in your filing status and rates. Open the Tax page "
                "→ Projection tab for a copy-paste config snippet. The harvest "
                "queue, offset budget, and trade traffic light still work "
                "without it."
            ),
            fix_url="/tax?view=projection",
            fix_form=None,
        )
    ]
