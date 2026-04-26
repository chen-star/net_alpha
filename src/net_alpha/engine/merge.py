from __future__ import annotations

from uuid import uuid4

from net_alpha.models.domain import WashSaleViolation
from net_alpha.models.realized_gl import RealizedGLLot


def _gl_to_violation(lot: RealizedGLLot, account_display: str) -> WashSaleViolation:
    """Convert a Schwab G/L lot flagged as wash_sale into a WashSaleViolation."""
    return WashSaleViolation(
        id=str(uuid4()),
        loss_trade_id="schwab_gl_" + lot.compute_natural_key()[:16],
        replacement_trade_id="schwab_gl_" + lot.compute_natural_key()[16:32],
        confidence="Confirmed",
        disallowed_loss=lot.disallowed_loss,
        matched_quantity=lot.quantity,
        loss_account=account_display,
        buy_account=account_display,  # Schwab same-account
        loss_sale_date=lot.closed_date,
        triggering_buy_date=lot.opened_date,
        ticker=lot.ticker,
        source="schwab_g_l",
    )


def _is_same_account(v: WashSaleViolation) -> bool:
    return v.loss_account == v.buy_account


def _matches_lot(v: WashSaleViolation, lot: RealizedGLLot, account_display: str) -> bool:
    """Engine violation is the 'same' wash sale Schwab is reporting."""
    return v.loss_account == account_display and v.ticker == lot.ticker and v.loss_sale_date == lot.closed_date


def _engine_v_with_overrides(v: WashSaleViolation, **overrides) -> WashSaleViolation:
    """Return a copy with mutated fields. WashSaleViolation is a Pydantic BaseModel."""
    data = v.model_dump()
    data.update(overrides)
    return WashSaleViolation(**data)


def merge_violations(
    *,
    engine_violations: list[WashSaleViolation],
    gl_lots_by_account: dict[int, list[RealizedGLLot]],
    substitute_tickers: dict[str, list[str]] | None = None,
    replacement_tickers: dict[str, str] | None = None,
) -> list[WashSaleViolation]:
    """Merge engine output with Schwab's per-lot verdicts.

    Rules:
      1. For each Schwab lot with wash_sale=True → emit Confirmed/schwab_g_l violation.
      2. For each engine violation:
         a. If same-account exact-ticker matches a Schwab lot:
              - Schwab said Yes → drop engine's (already covered by rule 1)
              - Schwab said No → engine downgraded to Unclear (likely engine bug, surface)
         b. If cross-account (loss_account != buy_account) → keep with source='engine'
         c. If same-account but not exact-ticker (substantially-identical/ETF pair),
            Schwab can't model this → surface as Unclear/engine
         d. If account has no G/L coverage → keep engine output unchanged
    """
    # substitute_tickers and replacement_tickers are accepted for forward-compat
    # but the current logic treats them implicitly via "no matching Schwab row".
    _ = substitute_tickers
    _ = replacement_tickers

    out: list[WashSaleViolation] = []

    # Index G/L lots by their account_display (the only field violations carry).
    lots_by_account_display: dict[str, list[RealizedGLLot]] = {}
    for lots in gl_lots_by_account.values():
        for lot in lots:
            lots_by_account_display.setdefault(lot.account_display, []).append(lot)

    # Rule 1: Schwab Yes → emit
    for account_display, lots in lots_by_account_display.items():
        for lot in lots:
            if lot.wash_sale:
                out.append(_gl_to_violation(lot, account_display))

    # Rule 2: process engine violations
    for v in engine_violations:
        same_account = _is_same_account(v)
        account_lots = lots_by_account_display.get(v.loss_account, [])

        if not account_lots:
            # 2d: no G/L coverage for this account → keep as-is, ensure source set
            out.append(_engine_v_with_overrides(v, source=v.source or "engine"))
            continue

        matching_lots = [lot for lot in account_lots if _matches_lot(v, lot, v.loss_account)]

        if same_account and matching_lots:
            schwab_yes = any(lot.wash_sale for lot in matching_lots)
            if schwab_yes:
                # 2a-yes: Schwab already covered this; drop engine's duplicate.
                continue
            # 2a-no: engine flagged but Schwab cleared — likely engine bug, surface as Unclear.
            out.append(_engine_v_with_overrides(v, confidence="Unclear", source="engine"))
            continue

        if not same_account:
            # 2b: cross-account → keep with engine source
            out.append(_engine_v_with_overrides(v, source="engine"))
            continue

        # 2c: same account but no matching Schwab lot row for this ticker — likely
        # substantially-identical (e.g. SPY loss + VOO buy). Surface as Unclear.
        out.append(_engine_v_with_overrides(v, confidence="Unclear", source="engine"))

    return out
