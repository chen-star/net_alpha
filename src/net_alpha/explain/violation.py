"""explain_violation — pure function building an ExplanationModel for a WashSaleViolation."""

from __future__ import annotations

from datetime import date as _date
from decimal import Decimal

from pydantic import BaseModel

from net_alpha.db.tables import WashSaleViolationRow
from net_alpha.explain import templates as tmpl


class TradeRow(BaseModel):
    """Lightweight trade descriptor for the explanation panel."""

    date: _date
    ticker: str
    action: str
    quantity: float
    proceeds: Decimal
    cost_basis: Decimal


class LotRef(BaseModel):
    """Reference to the Lot a disallowed loss rolled into."""

    lot_id: str
    acquired_date: _date
    adjusted_basis: Decimal


class AccountPair(BaseModel):
    loss_account: str
    buy_account: str


class ExplanationModel(BaseModel):
    summary: str
    rule_citation: str
    is_exempt: bool
    loss_trade: TradeRow
    triggering_buy: TradeRow
    days_between: int
    match_reason: str
    disallowed_or_notional: Decimal
    disallowed_math: str
    confidence: str
    confidence_reason: str
    adjusted_basis_target: LotRef | None
    cross_account: AccountPair | None


def _row_for(t) -> TradeRow:
    return TradeRow(
        date=t.date,
        ticker=t.ticker,
        action=t.action,
        quantity=t.quantity,
        proceeds=Decimal(str(t.proceeds)) if t.proceeds is not None else Decimal("0"),
        cost_basis=Decimal(str(t.cost_basis)) if t.cost_basis is not None else Decimal("0"),
    )


def _classify_match_kind(loss, buy) -> tuple[str, dict]:
    if loss.option_details is not None and buy.option_details is not None:
        return "option_chain", {
            "loss_ticker": loss.ticker,
            "buy_ticker": buy.ticker,
            "option_details": (
                f"{loss.ticker} {int(loss.option_details.strike)}{loss.option_details.call_put} "
                f"{loss.option_details.expiry.isoformat()}"
            ),
        }
    if loss.ticker != buy.ticker:
        return "etf_pair", {
            "loss_ticker": loss.ticker,
            "buy_ticker": buy.ticker,
            "group": None,
        }
    return "exact_ticker", {"loss_ticker": loss.ticker, "buy_ticker": buy.ticker}


def explain_violation(v: WashSaleViolationRow, *, repo) -> ExplanationModel:
    """Build an ExplanationModel for a real WashSaleViolation.

    Calls repo.get_trade_by_id(int) to resolve trade IDs.
    Cross-account detection compares Trade.account fields (not account_id ints),
    so no account-id resolution is needed.
    """
    loss = repo.get_trade_by_id(v.loss_trade_id)
    buy = repo.get_trade_by_id(v.replacement_trade_id)
    if loss is None or buy is None:
        raise ValueError(f"violation {v.id} references missing trades")

    days = (buy.date - loss.date).days
    match_kind, kwargs = _classify_match_kind(loss, buy)
    match_reason = tmpl.match_reason_text(match_kind=match_kind, **kwargs)

    disallowed = Decimal(str(v.disallowed_loss))
    loss_qty = float(loss.quantity)
    allocable = float(v.matched_quantity)

    # Full trade loss (cost_basis − proceeds) for the math string denominator.
    loss_proceeds = Decimal(str(loss.proceeds)) if loss.proceeds is not None else Decimal("0")
    loss_cost = Decimal(str(loss.cost_basis)) if loss.cost_basis is not None else Decimal("0")
    full_trade_loss = loss_cost - loss_proceeds  # positive when it's a real loss

    cross = None
    if loss.account != buy.account:
        cross = AccountPair(loss_account=loss.account, buy_account=buy.account)

    lot_ref = None
    lot_dict = repo.get_lot_row_dict_by_trade_id(buy.id)
    if lot_dict is not None:
        lot_ref = LotRef(
            lot_id=str(lot_dict["trade_id"]),
            acquired_date=_date.fromisoformat(lot_dict["trade_date"]),
            adjusted_basis=Decimal(str(lot_dict["adjusted_basis"])),
        )

    summary = (
        f"{loss.ticker} loss on {loss.date.isoformat()} disallowed by buy on "
        f"{buy.date.isoformat()} ({days} days later)."
    )

    if allocable != loss_qty:
        # Partial wash sale — show the allocation math using the full trade loss
        # as the starting amount, then prorate to the matched qty.
        disallowed_math = tmpl.disallowed_math_str(
            loss=full_trade_loss,
            allocable_qty=allocable,
            loss_qty=loss_qty,
        )
    else:
        disallowed_math = f"${tmpl._fmt(disallowed)}"

    return ExplanationModel(
        summary=summary,
        rule_citation=tmpl.rule_citation("regular"),
        is_exempt=False,
        loss_trade=_row_for(loss),
        triggering_buy=_row_for(buy),
        days_between=days,
        match_reason=match_reason,
        disallowed_or_notional=disallowed,
        disallowed_math=disallowed_math,
        confidence=v.confidence,
        confidence_reason=tmpl.confidence_reason(v.confidence, match_kind=match_kind, days_between=days),
        adjusted_basis_target=lot_ref,
        cross_account=cross,
    )
