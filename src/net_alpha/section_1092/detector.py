"""§1092 same-underlying offsetting-group detector.

Pure function. Inputs:
  * trades: every Trade in the DB (the detector reconstructs open positions
    by netting buys/sells per (account, ticker, option_details))
  * lots: every Lot in the DB (used to look up lot_id for long positions)

Outputs:
  * list[OffsettingGroup] — one per detected straddle/married-put/covered-call/etc.

v1 scope: only same-underlying, same-account offsets, 🟢-confidence tier.
Cross-account, correlated-ETF, and identified-straddle elections are deferred.

Detection rules (added in subsequent tasks):
  Task 3 — literal straddle (long call + long put)
  Task 4 — married put     (long stock + long put)
  Task 5 — covered call    (long stock + short call, gated by QCC test)
  Task 6 — vertical spread (long + short of same series, opposite legs)
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from decimal import Decimal

from net_alpha.models.domain import Lot, OffsettingGroup, OffsettingPosition, Trade


def _open_long_options(
    trades: list[Trade], lots: list[Lot]
) -> list[OffsettingPosition]:
    """Return one OffsettingPosition per long option contract still open.

    A long option contract is "open" if Σ(BTO qty) − Σ(STC qty) > 0 for that
    (account, ticker, strike, expiry, call_put). The matching Lot row supplies
    `lot_id` (the original BTO).
    """
    Key = tuple[str, str, float, str, str]  # (account, ticker, strike, expiry_iso, cp)
    net: dict[Key, Decimal] = defaultdict(lambda: Decimal("0"))
    earliest_lot: dict[Key, Lot] = {}

    for t in trades:
        if t.option_details is None:
            continue
        opt = t.option_details
        key: Key = (t.account, t.ticker, float(opt.strike), opt.expiry.isoformat(), opt.call_put)
        delta = Decimal(str(t.quantity))
        if t.action.lower() == "buy":
            net[key] += delta
        else:
            net[key] -= delta

    for lot in lots:
        if lot.option_details is None:
            continue
        opt = lot.option_details
        key = (lot.account, lot.ticker, float(opt.strike), opt.expiry.isoformat(), opt.call_put)
        prior = earliest_lot.get(key)
        if prior is None or lot.date < prior.date:
            earliest_lot[key] = lot

    positions: list[OffsettingPosition] = []
    for key, qty in net.items():
        if qty <= 0:
            continue
        _account, ticker, strike, _expiry_iso, cp = key
        lot = earliest_lot.get(key)
        if lot is None or lot.option_details is None:
            continue  # paired BTO/STC where lots were trimmed; skip
        positions.append(
            OffsettingPosition(
                kind="long_call" if cp == "C" else "long_put",
                trade_id=lot.trade_id,
                lot_id=lot.id,
                ticker=ticker,
                quantity=qty,
                opened_at=lot.date,
                side="long",
                option_strike=Decimal(str(strike)),
                option_expiry=lot.option_details.expiry,
                option_call_put=cp,
            )
        )
    return positions


def detect_offsetting_groups(
    *,
    trades: Iterable[Trade],
    lots: Iterable[Lot],
) -> list[OffsettingGroup]:
    """Return all 🟢-tier same-underlying offsetting groups currently open."""
    trades_list = list(trades)
    lots_list = list(lots)

    long_options = _open_long_options(trades_list, lots_list)
    by_lot_id: dict[str | None, Lot] = {lot.id: lot for lot in lots_list}

    by_ak: dict[tuple[str, str], list[OffsettingPosition]] = defaultdict(list)
    for p in long_options:
        lot = by_lot_id.get(p.lot_id)
        if lot is None:
            continue
        by_ak[(lot.account, p.ticker)].append(p)

    groups: list[OffsettingGroup] = []
    for (account, ticker), legs in by_ak.items():
        long_calls = [p for p in legs if p.kind == "long_call"]
        long_puts = [p for p in legs if p.kind == "long_put"]
        if long_calls and long_puts:
            groups.append(
                OffsettingGroup(
                    account=account,
                    ticker=ticker,
                    positions=long_calls + long_puts,
                    kind="literal_straddle",
                    confidence="Confirmed",
                    rule_citation="IRC §1092(c)(2)(A)",
                    reasoning="Long call and long put open simultaneously on the same underlying — "
                    "textbook straddle; loss on either leg may be deferred under §1092(a)(1).",
                )
            )

    return groups
