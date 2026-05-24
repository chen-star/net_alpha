from __future__ import annotations

from collections import defaultdict
from datetime import date as _date
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from net_alpha.engine.matcher import get_match_confidence, is_within_wash_sale_window
from net_alpha.models.accounts import AccountType
from net_alpha.models.domain import DetectionResult, ExemptMatch, Lot, Trade, WashSaleViolation

_CENT = Decimal("0.01")


def _apportion_disallowed_cents(total_loss: Decimal, allocations: list[Decimal]) -> list[Decimal]:
    """Apportion ``total_loss`` (in dollars, already quantized to cents) across
    a list of ``allocations`` (per-match allocable quantities) so that the
    rounded-to-cents per-match amounts SUM EXACTLY to ``total_loss``.

    Audit #40: the previous implementation computed
    ``round(allocable * loss_per_unit, 2)`` independently per match, which
    drifted by up to one cent per match (e.g. three qty-1 buys against a $1.00
    loss → 0.33 + 0.33 + 0.33 = 0.99). Use largest-remainder rounding (Hare
    quota): truncate down per match to whole cents, then distribute the
    residual cents one-at-a-time to the matches with the largest fractional
    remainders. Stable across recompute cycles.
    """
    qty_total = sum(allocations)
    if qty_total <= 0:
        return [Decimal("0")] * len(allocations)

    # Exact per-match share in cents (Decimal arithmetic).
    total_cents = (total_loss * Decimal(100)).to_integral_value(rounding=ROUND_HALF_UP)
    raw_shares = [a * total_cents / qty_total for a in allocations]
    floor_cents = [int(s.to_integral_value(rounding="ROUND_FLOOR")) for s in raw_shares]
    residual = int(total_cents) - sum(floor_cents)

    # Distribute residual cents to the matches with the largest fractional
    # remainder; ties broken by larger allocation (so the biggest match takes
    # the cent first), then by original index for stability.
    fractions = [
        (
            s - Decimal(fc),
            allocations[i],
            i,
        )
        for i, (s, fc) in enumerate(zip(raw_shares, floor_cents))
    ]
    ordered = sorted(fractions, key=lambda x: (-x[0], -x[1], x[2]))
    cents_per_match = list(floor_cents)
    for k in range(residual):
        # Cap residual distribution to the available list — should always
        # match since residual <= len(allocations) by construction.
        if k >= len(ordered):
            break
        _frac, _alloc, idx = ordered[k]
        cents_per_match[idx] += 1

    return [Decimal(c) / Decimal(100) for c in cents_per_match]


def _lot_key(t: Trade) -> tuple:
    """FIFO consumption key — equities by (account, ticker); options by full contract."""
    if t.option_details is not None:
        o = t.option_details
        return (t.account, t.ticker, o.strike, o.expiry.isoformat(), o.call_put)
    return (t.account, t.ticker, None, None, None)


def _is_tax_advantaged(account: str, account_types: dict[str, AccountType] | None) -> bool:
    """Resolve an account label to its tax-advantaged status. Defaults to False
    (taxable) when the lookup is missing — matches pre-Rev. Rul. 2008-5 behavior."""
    if not account_types:
        return False
    t = account_types.get(account, AccountType.TAXABLE)
    return t.is_tax_advantaged


def detect_wash_sales(
    trades: list[Trade],
    etf_pairs: dict[str, list[str]],
    account_types: dict[str, AccountType] | None = None,
) -> DetectionResult:
    """Detect wash sales across all trades. Pure function — no I/O.

    Algorithm:
    1. Find all loss sales, sorted by date
    2. Create lots from all buy trades
    3. For each loss sale, match against candidates in FIFO order
    4. Allocate disallowed loss and adjust replacement lot basis
    5. Tack holding period of replacement lot per IRC §1223(4): the FIFO-matched
       loss-side lot's effective acquired date is propagated onto the replacement.

    Rev. Rul. 2008-5 (IRA trap): when the replacement leg sits in a tax-advantaged
    account (IRA / Roth / 401(k) / HSA) per ``account_types``, the violation is
    classified ``kind="permanent_ira"`` and §1091(d)'s basis rollover does NOT
    apply — the disallowed loss is permanently lost. Also: a loss sale INSIDE a
    tax-advantaged account is not a taxable event, so we skip §1091 entirely on
    that loss leg.
    """
    # Skip the assigned-put synthetic STO/BTC pair from loss/candidate scans:
    # they have synthetic proceeds/cost (premium and 0 respectively) used only
    # to keep cash flow / open-option counts honest, not to represent
    # independent realized events the wash-sale rule applies to.
    _SYNTHETIC_SOURCES = {"option_short_open_assigned", "option_short_close_assigned"}

    # Create lots from buys — track remaining allocable quantity per lot.
    # `option_short_close` (BTC) is a Buy that closes a short option position;
    # it should NOT seed a new long lot, so it is excluded here. (It also
    # naturally falls out of wash-sale candidacy below since `lot_remaining`
    # never lists it.)
    lots: dict[str, Lot] = {}
    lot_remaining: dict[str, float] = {}
    # Parallel FIFO tracker: how much of each buy lot is still unconsumed by
    # later sells (gain or loss). Used only to find the holding-period donor
    # for §1223(4) tacking — independent of ``lot_remaining`` which tracks
    # replacement-side allocations for wash-sale matches.
    fifo_remaining: dict[str, float] = {}
    _NO_LOT_BUYS = {"option_short_close", "option_short_close_assigned"}
    buys_by_key: dict[tuple, list[Trade]] = defaultdict(list)
    for t in trades:
        if t.is_buy() and t.basis_source not in _NO_LOT_BUYS:
            lot = Lot.from_trade(t)
            lots[t.id] = lot
            lot_remaining[t.id] = t.quantity
            fifo_remaining[t.id] = t.quantity
            buys_by_key[_lot_key(t)].append(t)
    for chain in buys_by_key.values():
        chain.sort(key=lambda x: x.date)

    def consume_fifo_acquired_date(sell: Trade) -> _date | None:
        """FIFO-consume buys of the same key with date <= sell.date; return the
        earliest effective acquired date of the consumed lots (or None)."""
        chain = buys_by_key.get(_lot_key(sell), [])
        qty_to_match = sell.quantity
        earliest: _date | None = None
        for buy in chain:
            if buy.date > sell.date:
                break
            available = fifo_remaining.get(buy.id, 0)
            if available <= 0:
                continue
            take = min(qty_to_match, available)
            fifo_remaining[buy.id] -= take
            eff = lots[buy.id].effective_acquired_date()
            if earliest is None or eff < earliest:
                earliest = eff
            qty_to_match -= take
            if qty_to_match <= 0:
                break
        return earliest

    # Count basis_unknown trades for the warning
    basis_unknown_count = sum(1 for t in trades if t.basis_unknown)

    violations: list[WashSaleViolation] = []
    exempt_matches: list[ExemptMatch] = []

    # Walk ALL sells in date order; FIFO-consume buys so the per-loss
    # acquired-date lookup is correct even when prior gain sells have already
    # drained the earliest lots. Loss sells then run wash-sale detection.
    all_sells = sorted(
        [t for t in trades if t.is_sell() and t.basis_source not in _SYNTHETIC_SOURCES],
        key=lambda t: t.date,
    )

    for sell in all_sells:
        loss_side_acquired = consume_fifo_acquired_date(sell)
        if not sell.is_loss():
            continue

        loss_sale = sell
        # Rev. Rul. 2008-5: a loss inside a tax-advantaged account is not a
        # taxable event (no §61 income → no §165 loss). §1091 has nothing to
        # disallow, so skip detection on the loss leg entirely.
        if _is_tax_advantaged(loss_sale.account, account_types):
            continue
        # Fallback: orphan loss sell with no prior buy → use sell date.
        if loss_side_acquired is None:
            loss_side_acquired = loss_sale.date

        remaining_qty = loss_sale.quantity

        # Find candidates within window, sorted by date (FIFO)
        candidates = _find_candidates(loss_sale, trades, etf_pairs)

        # Audit #40: first pass — collect each match's allocable quantity
        # WITHOUT computing the disallowed dollars per match. Then apportion
        # the loss-sale's total loss across matches using largest-remainder
        # rounding in integer cents so the per-match dollar amounts sum
        # exactly to the loss. Avoids cumulative per-unit float drift.
        match_plan: list[tuple[Trade, str, float]] = []  # (candidate, confidence, allocable)
        for candidate, confidence in candidates:
            if remaining_qty <= 0:
                break
            if candidate.is_buy() and candidate.id in lot_remaining:
                available = lot_remaining[candidate.id]
                if available <= 0:
                    continue
                allocable = min(remaining_qty, available)
                lot_remaining[candidate.id] -= allocable
            elif candidate.is_sell() and candidate.is_option() and candidate.option_details.call_put == "P":
                allocable = min(remaining_qty, candidate.quantity)
            else:
                continue
            match_plan.append((candidate, confidence, allocable))
            remaining_qty -= allocable

        # Apportion the *matched portion* of the loss across each match using
        # largest-remainder rounding. Pro-rate the loss to the matched
        # quantity first (so a 40-of-100 partial wash sale disallows 40% of
        # the loss), then split that pro-rated amount across the matched
        # candidates with no penny drift.
        total_loss = Decimal(str(loss_sale.loss_amount()))
        total_qty = Decimal(str(loss_sale.quantity))
        matched_qty = sum((Decimal(str(a)) for _, _, a in match_plan), Decimal("0"))
        if matched_qty == 0 or total_qty == 0:
            matched_loss = Decimal("0")
        else:
            matched_loss = (total_loss * matched_qty / total_qty).quantize(_CENT, rounding=ROUND_HALF_UP)
        allocations_dec = [Decimal(str(a)) for _, _, a in match_plan]
        disallowed_per_match = _apportion_disallowed_cents(matched_loss, allocations_dec)

        for (candidate, confidence, allocable), disallowed_dec in zip(match_plan, disallowed_per_match):
            disallowed = float(disallowed_dec)

            if loss_sale.is_section_1256 or candidate.is_section_1256:
                exempt_matches.append(
                    ExemptMatch(
                        loss_trade_id=loss_sale.id,
                        triggering_buy_id=candidate.id,
                        exempt_reason="section_1256",
                        rule_citation="IRC §1256(c)",
                        notional_disallowed=disallowed_dec,
                        confidence=confidence,
                        matched_quantity=allocable,
                        loss_account=loss_sale.account,
                        buy_account=candidate.account,
                        loss_sale_date=loss_sale.date,
                        triggering_buy_date=candidate.date,
                        ticker=loss_sale.ticker,
                    )
                )
                # do NOT adjust replacement-lot basis — §1256 is exempt, no rollover
            else:
                # Rev. Rul. 2008-5: if the replacement leg is in a tax-
                # advantaged account, §1091(a) still disallows the loss but
                # §1091(d)'s basis rollover can't apply — the loss is gone.
                is_permanent = _is_tax_advantaged(candidate.account, account_types)
                # Sold-put trigger: §1091 still disallows the loss, but the
                # replacement leg is a "contract to acquire" (no holding lot
                # exists in our schema to roll basis into). We mark these as
                # "deferred_to_contract" so reporting can distinguish them
                # from ordinary equity rollovers — they require manual
                # tracking until the put is closed or assigned.
                is_sold_put_trigger = (
                    candidate.is_sell()
                    and candidate.is_option()
                    and candidate.option_details is not None
                    and candidate.option_details.call_put == "P"
                )
                if is_permanent:
                    kind = "permanent_ira"
                elif is_sold_put_trigger:
                    kind = "deferred_to_contract"
                else:
                    kind = "deferred"

                violations.append(
                    WashSaleViolation(
                        loss_trade_id=loss_sale.id,
                        replacement_trade_id=candidate.id,
                        confidence=confidence,
                        disallowed_loss=disallowed,
                        matched_quantity=allocable,
                        loss_account=loss_sale.account,
                        buy_account=candidate.account,
                        loss_sale_date=loss_sale.date,
                        triggering_buy_date=candidate.date,
                        ticker=loss_sale.ticker,
                        kind=kind,
                    )
                )

                # Adjust replacement lot basis + tack holding period (§1223(4)),
                # but ONLY for ordinary deferred wash sales. Permanent
                # (IRA-trap) ones have no §1091(d) rollover. Sold-put triggers
                # ("deferred_to_contract") have no equity lot to mutate; the
                # rolled basis must attach to the option contract — out of
                # scope for v1.
                if not is_permanent and not is_sold_put_trigger and candidate.id in lots:
                    lots[candidate.id].adjusted_basis += disallowed
                    # IRC §1223(4): the loss-leg's holding period "shall be
                    # included" in the replacement lot's holding period. Apply
                    # this additively — shift the replacement's effective
                    # acquired date backward by the loss-leg's HP-in-days — so
                    # chained wash sales accumulate correctly, and an
                    # earliest-wins comparison can never under- nor over-tack.
                    # (Audit #9: previously, the engine took
                    # ``min(loss_side_acquired, current_eff)``, which both
                    # under-tacked when FIFO consumed a newer loss leg into an
                    # older replacement AND over-tacked during the rebuy gap
                    # when the replacement was bought AFTER the loss sale.)
                    loss_leg_hp_days = (loss_sale.date - loss_side_acquired).days
                    if loss_leg_hp_days > 0:
                        current_eff = lots[candidate.id].effective_acquired_date()
                        new_tacked = current_eff - timedelta(days=loss_leg_hp_days)
                        lots[candidate.id].tacked_acquired_date = new_tacked

    return DetectionResult(
        violations=violations,
        lots=list(lots.values()),
        basis_unknown_count=basis_unknown_count,
        exempt_matches=exempt_matches,
    )


def _find_candidates(
    loss_sale: Trade,
    all_trades: list[Trade],
    etf_pairs: dict[str, list[str]],
) -> list[tuple[Trade, str]]:
    """Find and sort candidate triggers for a loss sale.

    Returns (trade, confidence) pairs in FIFO order.
    """
    candidates: list[tuple[Trade, str]] = []
    for t in all_trades:
        if t.id == loss_sale.id:
            continue
        if not is_within_wash_sale_window(loss_sale.date, t.date):
            continue
        confidence = get_match_confidence(loss_sale, t, etf_pairs)
        if confidence is not None:
            candidates.append((t, confidence))
    candidates.sort(key=lambda x: x[0].date)
    return candidates


def detect_in_window(
    trades: list[Trade],
    window_start: _date,
    window_end: _date,
    etf_pairs: dict[str, list[str]],
    account_types: dict[str, AccountType] | None = None,
) -> DetectionResult:
    """Run the full detection algorithm but emit only violations whose
    loss_sale_date is within [window_start, window_end].

    `trades` MUST include all trades within ±30 days of [window_start, window_end]
    so cross-window matching is correct. The caller is responsible for that.

    ``account_types`` (Rev. Rul. 2008-5) is forwarded to ``detect_wash_sales``;
    missing or empty defaults to all-taxable behavior.
    """
    full = detect_wash_sales(trades, etf_pairs, account_types=account_types)
    in_window = [
        v for v in full.violations if v.loss_sale_date is not None and window_start <= v.loss_sale_date <= window_end
    ]
    in_window_exempt = [
        em
        for em in full.exempt_matches
        if em.loss_sale_date is not None and window_start <= em.loss_sale_date <= window_end
    ]
    # Lots are recomputed downstream from the full trade set, so we still return all.
    return DetectionResult(
        violations=in_window,
        lots=full.lots,
        basis_unknown_count=full.basis_unknown_count,
        exempt_matches=in_window_exempt,
    )
