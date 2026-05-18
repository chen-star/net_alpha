from __future__ import annotations

from collections.abc import Mapping

from net_alpha.models.domain import Trade

AssignmentKey = tuple[str, str, str, float]
SellBasisBlindKey = tuple[str, str, str, float, str]


def filter_new(trades: list[Trade], known_natural_keys: set[str]) -> list[Trade]:
    """Return only trades whose natural key is not in known_natural_keys."""
    return [t for t in trades if t.compute_natural_key() not in known_natural_keys]


def sell_basis_blind_key(t: Trade) -> SellBasisBlindKey:
    """``(account, ticker, date_iso, qty, proceeds_str)`` for a Sell trade.

    ``compute_natural_key`` includes ``cost_basis``, so a Schwab re-export
    that gains a populated ``Cost Basis`` column produces a *new* key for
    the same logical sell and the second row inserts as a duplicate. This
    basis-blind key catches that case — two sells with identical
    (account, ticker, date, qty, proceeds) are the same logical close
    regardless of which export ran the basis column.
    """
    return (
        t.account,
        t.ticker,
        t.date.isoformat(),
        float(t.quantity),
        str(t.proceeds if t.proceeds is not None else ""),
    )


def filter_sell_basis_drift_duplicates(
    trades: list[Trade],
    existing_keys: set[SellBasisBlindKey],
) -> list[Trade]:
    """Drop equity Sells whose basis-blind key matches an existing Sell.

    Intended for re-imports where Schwab's export gained a ``Cost Basis``
    column between exports — same logical sell, drifted natural_key,
    silently doubled until this pass runs.
    """
    out: list[Trade] = []
    for t in trades:
        if t.action != "Sell" or t.option_details is not None:
            out.append(t)
            continue
        if sell_basis_blind_key(t) in existing_keys:
            continue
        out.append(t)
    return out


def filter_assignment_duplicates(
    trades: list[Trade],
    *,
    existing_assignments: set[AssignmentKey] | Mapping[AssignmentKey, int],
) -> list[Trade]:
    """Drop plain equity Buys that duplicate an existing put_assignment row.

    Schwab's transactions CSV records a put assignment as two correlated rows:
    an ``Assigned`` option row AND a ``Buy`` of the underlying at strike.
    SchwabParser converts the Assigned row to a synthetic put_assignment
    trade with premium-adjusted basis (strike*qty - collected premium); the
    raw underlying-Buy row is then absorbed because the parser sees the
    matching offset in ``_put_assignment_basis_offsets``.

    On a *partial* re-import (e.g. the user re-exports a narrower date range
    that omits the Assigned option row) only the underlying-Buy row reaches
    the parser, which emits it as a plain Buy at unadjusted cost_basis
    (basis_source='unknown'). Natural-key dedup misses because cost_basis
    is part of the hash. This second-pass filter catches the double by
    keying on (account, ticker, date, qty) against existing put_assignment
    trades.

    Only basis_source='unknown' equity Buys are eligible. A Buy already
    classified by the parser (g_l, transfer_in, etc.) is presumed correct
    and is not dropped. Option rows are also never dropped.

    Strike isn't part of the dedup key (the underlying-Buy row from a
    partial re-import doesn't carry the option strike), so when two
    different-strike puts on the same ticker are assigned same-day at the
    same contract count, both existing put_assignment trades share the key.
    To avoid silently losing a genuinely-new lot in that ambiguous case,
    callers can pass a ``Mapping[key, count]`` instead of a set; when count
    >= 2 the filter leaves matching Buys alone so the user can manually
    resolve any duplicates rather than lose basis.
    """
    if isinstance(existing_assignments, Mapping):
        counts = dict(existing_assignments)
    else:
        counts = {key: 1 for key in existing_assignments}

    out: list[Trade] = []
    for t in trades:
        if t.option_details is not None:
            out.append(t)
            continue
        if t.action != "Buy" or t.basis_source != "unknown":
            out.append(t)
            continue
        key = (t.account, t.ticker, t.date.isoformat(), float(t.quantity))
        existing_count = counts.get(key, 0)
        if existing_count == 1:
            continue  # the common case: single put_assignment for this key
        out.append(t)  # 0 (no match) or >=2 (ambiguous) — keep the Buy
    return out
