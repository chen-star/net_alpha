from __future__ import annotations

from net_alpha.models.domain import Trade


def filter_new(trades: list[Trade], known_natural_keys: set[str]) -> list[Trade]:
    """Return only trades whose natural key is not in known_natural_keys."""
    return [t for t in trades if t.compute_natural_key() not in known_natural_keys]


def filter_assignment_duplicates(
    trades: list[Trade],
    *,
    existing_assignments: set[tuple[str, str, str, float]],
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
    """
    out: list[Trade] = []
    for t in trades:
        if t.option_details is not None:
            out.append(t)
            continue
        if t.action != "Buy" or t.basis_source != "unknown":
            out.append(t)
            continue
        key = (t.account, t.ticker, t.date.isoformat(), float(t.quantity))
        if key in existing_assignments:
            continue
        out.append(t)
    return out
