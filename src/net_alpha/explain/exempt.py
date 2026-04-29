"""explain_exempt — pure function building an ExplanationModel for an ExemptMatch."""
from __future__ import annotations

from decimal import Decimal

from net_alpha.db.tables import ExemptMatchRow
from net_alpha.explain import templates as tmpl
from net_alpha.explain.violation import (
    AccountPair,
    ExplanationModel,
    TradeRow,
    _classify_match_kind,
)


def _row_for(t) -> TradeRow:
    return TradeRow(
        date=t.date,
        ticker=t.ticker,
        action=t.action,
        quantity=t.quantity,
        proceeds=Decimal(str(t.proceeds)) if t.proceeds is not None else Decimal("0"),
        cost_basis=Decimal(str(t.cost_basis)) if t.cost_basis is not None else Decimal("0"),
    )


def explain_exempt(em: ExemptMatchRow, *, repo) -> ExplanationModel:
    """Build an ExplanationModel for an ExemptMatch (e.g., §1256).

    Sets is_exempt=True and adjusted_basis_target=None — exempt matches do not
    roll disallowed losses into a replacement lot's cost basis.
    """
    loss = repo.get_trade_by_id(em.loss_trade_id)
    buy = repo.get_trade_by_id(em.triggering_buy_id)
    if loss is None or buy is None:
        raise ValueError(f"exempt match {em.id} references missing trades")

    days = (buy.date - loss.date).days
    match_kind, kwargs = _classify_match_kind(loss, buy)
    match_reason = tmpl.match_reason_text(match_kind=match_kind, **kwargs)
    notional = Decimal(str(em.notional_disallowed))
    loss_qty = float(loss.quantity)
    allocable = float(em.matched_quantity)

    cross = None
    if em.loss_account != em.buy_account:
        cross = AccountPair(loss_account=em.loss_account, buy_account=em.buy_account)

    summary = (
        f"{em.ticker} match — exempt under §1256(c). "
        f"Index options are not subject to §1091."
    )

    if allocable != loss_qty:
        disallowed_math = tmpl.disallowed_math_str(
            loss=notional,
            allocable_qty=allocable,
            loss_qty=loss_qty,
        )
    else:
        disallowed_math = f"${tmpl._fmt(notional)}"

    return ExplanationModel(
        summary=summary,
        rule_citation=tmpl.rule_citation(em.exempt_reason),
        is_exempt=True,
        loss_trade=_row_for(loss),
        triggering_buy=_row_for(buy),
        days_between=days,
        match_reason=match_reason,
        disallowed_or_notional=notional,
        disallowed_math=disallowed_math,
        confidence=em.confidence,
        confidence_reason=tmpl.confidence_reason(em.confidence, match_kind=match_kind, days_between=days),
        adjusted_basis_target=None,
        cross_account=cross,
    )
