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


def _open_long_stock(
    trades: list[Trade], lots: list[Lot]
) -> list[OffsettingPosition]:
    """Return one OffsettingPosition per (account, ticker) with net long equity."""
    qty: dict[tuple[str, str], Decimal] = defaultdict(lambda: Decimal("0"))
    earliest_lot: dict[tuple[str, str], Lot] = {}

    for t in trades:
        if t.option_details is not None:
            continue
        delta = Decimal(str(t.quantity))
        if t.action.lower() == "buy":
            qty[(t.account, t.ticker)] += delta
        else:
            qty[(t.account, t.ticker)] -= delta

    for lot in lots:
        if lot.option_details is not None:
            continue
        key = (lot.account, lot.ticker)
        prior = earliest_lot.get(key)
        if prior is None or lot.date < prior.date:
            earliest_lot[key] = lot

    positions: list[OffsettingPosition] = []
    for (account, ticker), q in qty.items():
        if q <= 0:
            continue
        lot = earliest_lot.get((account, ticker))
        if lot is None:
            continue
        positions.append(
            OffsettingPosition(
                kind="long_stock",
                trade_id=lot.trade_id,
                lot_id=lot.id,
                ticker=ticker,
                quantity=q,
                opened_at=lot.date,
                side="long",
            )
        )
    return positions


def _open_short_options(trades: list[Trade]) -> list[OffsettingPosition]:
    """Return one OffsettingPosition per short option contract still open.

    Short option contracts have no Lot row; lot_id stays None and trade_id
    points to the most recent STO that still has open contracts.
    """
    Key = tuple[str, str, float, str, str]  # (account, ticker, strike, expiry_iso, cp)
    net: dict[Key, Decimal] = defaultdict(lambda: Decimal("0"))
    latest_sto: dict[Key, Trade] = {}

    for t in trades:
        if t.option_details is None:
            continue
        opt = t.option_details
        key: Key = (t.account, t.ticker, float(opt.strike), opt.expiry.isoformat(), opt.call_put)
        delta = Decimal(str(t.quantity))
        if t.action.lower() == "buy":
            net[key] += delta  # BTC closes short
        else:
            net[key] -= delta  # STO opens short
            prior = latest_sto.get(key)
            if prior is None or t.date > prior.date:
                latest_sto[key] = t

    positions: list[OffsettingPosition] = []
    for key, qty in net.items():
        if qty >= 0:
            continue  # not net short
        account, ticker, strike, expiry_iso, cp = key
        sto = latest_sto.get(key)
        if sto is None:
            continue
        positions.append(
            OffsettingPosition(
                kind="short_call" if cp == "C" else "short_put",
                trade_id=sto.id,
                lot_id=None,
                ticker=ticker,
                quantity=-qty,
                opened_at=sto.date,
                side="short",
                option_strike=Decimal(str(strike)),
                option_expiry=sto.option_details.expiry,
                option_call_put=cp,
            )
        )
    return positions


def detect_offsetting_groups(
    *,
    trades: Iterable[Trade],
    lots: Iterable[Lot],
    underlying_prices: dict[str, Decimal] | None = None,
) -> list[OffsettingGroup]:
    """Return all 🟢-tier same-underlying offsetting groups currently open.

    *underlying_prices*: optional ticker → current price map. Required for the
    QCC test on covered calls; if absent or missing for a ticker, covered-call
    groups are still emitted (with "QCC test skipped" in the reasoning) so
    the user is warned conservatively.
    """
    from net_alpha.section_1092.qcc import is_qualified_covered_call

    trades_list = list(trades)
    lots_list = list(lots)
    prices = underlying_prices or {}

    long_options = _open_long_options(trades_list, lots_list)
    long_stock = _open_long_stock(trades_list, lots_list)
    short_options = _open_short_options(trades_list)
    by_lot_id: dict[str | None, Lot] = {lot.id: lot for lot in lots_list}

    # Build (account, ticker) → legs map. Long-side legs derive their account
    # from their lot; short-option legs carry account on trade_id, so we look
    # them up from the trades list.
    trade_by_id: dict[str, Trade] = {t.id: t for t in trades_list}
    by_ak: dict[tuple[str, str], list[OffsettingPosition]] = defaultdict(list)
    for p in long_options + long_stock:
        lot = by_lot_id.get(p.lot_id)
        if lot is None:
            continue
        by_ak[(lot.account, p.ticker)].append(p)
    for p in short_options:
        sto = trade_by_id.get(p.trade_id)
        if sto is None:
            continue
        by_ak[(sto.account, p.ticker)].append(p)

    groups: list[OffsettingGroup] = []
    for (account, ticker), legs in by_ak.items():
        long_calls = [p for p in legs if p.kind == "long_call"]
        long_puts = [p for p in legs if p.kind == "long_put"]
        long_stk = [p for p in legs if p.kind == "long_stock"]
        short_calls = [p for p in legs if p.kind == "short_call"]
        short_puts = [p for p in legs if p.kind == "short_put"]

        # Rule 1 — literal straddle.
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

        # Rule 2 — married put.
        if long_stk and long_puts:
            groups.append(
                OffsettingGroup(
                    account=account,
                    ticker=ticker,
                    positions=long_stk + long_puts,
                    kind="married_put",
                    confidence="Confirmed",
                    rule_citation="IRC §1092(c)(2)(A)",
                    reasoning="Long stock paired with long put on the same underlying — the put "
                    "substantially diminishes the stock's loss risk, so the pair is an §1092 straddle.",
                )
            )

        # Rule 3 — covered call (only when QCC test FAILS, or skipped).
        if long_stk and short_calls:
            for sc in short_calls:
                price = prices.get(ticker)
                if price is None:
                    reasoning = (
                        "Long stock + short call — QCC test skipped (no underlying price available); "
                        "if the call is non-qualified, this is an §1092 straddle. Verify with current price."
                    )
                else:
                    sto = trade_by_id.get(sc.trade_id)
                    if sto is None or sc.option_strike is None or sc.option_expiry is None:
                        continue
                    dte = (sc.option_expiry - sto.date).days
                    qualifies, reason = is_qualified_covered_call(
                        underlying_price_at_write=price,
                        strike=sc.option_strike,
                        days_to_expiry_at_write=dte,
                    )
                    if qualifies:
                        continue  # QCC → exempt from §1092
                    reasoning = (
                        f"Long stock + short call that fails QCC: {reason}. "
                        "Pair is an §1092 straddle; LT clock on the stock is suspended (§1092(f))."
                    )
                groups.append(
                    OffsettingGroup(
                        account=account,
                        ticker=ticker,
                        positions=long_stk + [sc],
                        kind="covered_call",
                        confidence="Confirmed",
                        rule_citation="IRC §1092(c)(4)",
                        reasoning=reasoning,
                    )
                )

        # Rule 4 — vertical spread (same expiry, opposite legs, same option type).
        for lc in long_calls:
            for sc in short_calls:
                if lc.option_expiry is None or sc.option_expiry is None:
                    continue
                if lc.option_expiry != sc.option_expiry:
                    continue
                groups.append(
                    OffsettingGroup(
                        account=account,
                        ticker=ticker,
                        positions=[lc, sc],
                        kind="vertical_spread",
                        confidence="Confirmed",
                        rule_citation="IRC §1092(c)(2)(A)",
                        reasoning="Long call + short call (same expiry) — short leg substantially "
                        "diminishes loss risk on the long leg; pair is an §1092 straddle.",
                    )
                )
        for lp in long_puts:
            for sp in short_puts:
                if lp.option_expiry is None or sp.option_expiry is None:
                    continue
                if lp.option_expiry != sp.option_expiry:
                    continue
                groups.append(
                    OffsettingGroup(
                        account=account,
                        ticker=ticker,
                        positions=[lp, sp],
                        kind="vertical_spread",
                        confidence="Confirmed",
                        rule_citation="IRC §1092(c)(2)(A)",
                        reasoning="Long put + short put (same expiry) — short leg substantially "
                        "diminishes loss risk on the long leg; pair is an §1092 straddle.",
                    )
                )

    return groups
