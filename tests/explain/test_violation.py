from datetime import date
from decimal import Decimal

from net_alpha.db.tables import WashSaleViolationRow
from net_alpha.explain import ExplanationModel
from net_alpha.explain.violation import explain_violation
from net_alpha.models.domain import OptionDetails, Trade


class _FakeRepo:
    """Minimal stub: resolves trade ids to Trade pydantic models."""

    def __init__(self, trades):
        self._by_id = {int(t.id): t for t in trades}

    def get_trade_by_id(self, tid):
        return self._by_id.get(int(tid)) if tid is not None else None

    def get_lot_row_dict_by_trade_id(self, tid):
        return None


def _trade(
    id_: str,
    ticker: str,
    action: str,
    d: date,
    qty: float,
    proceeds: Decimal,
    cost: Decimal,
    *,
    opt: OptionDetails | None = None,
):
    return Trade(
        id=id_,
        date=d,
        account="schwab/personal",
        ticker=ticker,
        action=action,
        quantity=qty,
        proceeds=float(proceeds),
        cost_basis=float(cost),
        option_details=opt,
    )


def test_explain_violation_exact_ticker_full_match():
    loss = _trade("1", "TSLA", "Sell", date(2024, 9, 15), 100, Decimal("18757"), Decimal("20000"))
    buy = _trade("2", "TSLA", "Buy", date(2024, 9, 22), 100, Decimal("19000"), Decimal("19000"))
    repo = _FakeRepo([loss, buy])
    v = WashSaleViolationRow(
        id=1,
        loss_trade_id=1,
        replacement_trade_id=2,
        confidence="Confirmed",
        disallowed_loss=Decimal("1243"),
        matched_quantity=100.0,
        loss_account_id=1,
        buy_account_id=1,
        loss_sale_date="2024-09-15",
        triggering_buy_date="2024-09-22",
        ticker="TSLA",
    )
    e = explain_violation(v, repo=repo)
    assert isinstance(e, ExplanationModel)
    assert e.is_exempt is False
    assert e.rule_citation == "IRC §1091(a) — Pub 550 p.59"
    assert e.days_between == 7
    assert "exact ticker" in e.match_reason.lower()
    assert e.disallowed_or_notional == Decimal("1243")
    assert "Confirmed" in e.confidence_reason
    assert e.cross_account is None  # same account both sides


def test_explain_violation_cross_account():
    loss = _trade("3", "TSLA", "Sell", date(2024, 9, 15), 100, Decimal("18757"), Decimal("20000"))
    buy = _trade("4", "TSLA", "Buy", date(2024, 9, 22), 100, Decimal("19000"), Decimal("19000"))
    buy = buy.model_copy(update={"account": "schwab/roth"})
    repo = _FakeRepo([loss, buy])
    v = WashSaleViolationRow(
        id=2,
        loss_trade_id=3,
        replacement_trade_id=4,
        confidence="Confirmed",
        disallowed_loss=Decimal("1243"),
        matched_quantity=100.0,
        loss_account_id=1,
        buy_account_id=2,
        loss_sale_date="2024-09-15",
        triggering_buy_date="2024-09-22",
        ticker="TSLA",
    )
    e = explain_violation(v, repo=repo)
    assert e.cross_account is not None
    # cross_account exposes the actual account display strings; the explainer
    # should resolve them via repo (since the row stores int IDs). Our fake
    # repo doesn't have account resolution, so the explainer should fall back
    # to using the Trade.account field of the loaded trades.
    assert e.cross_account.loss_account == "schwab/personal"
    assert e.cross_account.buy_account == "schwab/roth"


def test_explain_violation_partial_match():
    loss = _trade("5", "TSLA", "Sell", date(2024, 9, 15), 100, Decimal("18757"), Decimal("20000"))
    buy = _trade("6", "TSLA", "Buy", date(2024, 9, 22), 50, Decimal("9500"), Decimal("9500"))
    repo = _FakeRepo([loss, buy])
    v = WashSaleViolationRow(
        id=3,
        loss_trade_id=5,
        replacement_trade_id=6,
        confidence="Confirmed",
        disallowed_loss=Decimal("621.50"),
        matched_quantity=50.0,
        loss_account_id=1,
        buy_account_id=1,
        loss_sale_date="2024-09-15",
        triggering_buy_date="2024-09-22",
        ticker="TSLA",
    )
    e = explain_violation(v, repo=repo)
    assert "50" in e.disallowed_math
    assert "100" in e.disallowed_math
    assert "$621.50" in e.disallowed_math
