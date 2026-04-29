from datetime import date
from decimal import Decimal

from net_alpha.db.tables import ExemptMatchRow
from net_alpha.explain import ExplanationModel
from net_alpha.explain.exempt import explain_exempt
from net_alpha.models.domain import OptionDetails, Trade


class _FakeRepo:
    def __init__(self, trades):
        self._by_id = {int(t.id): t for t in trades}

    def get_trade_by_id(self, tid):
        return self._by_id.get(int(tid)) if tid is not None else None

    def get_lot_row_dict_by_trade_id(self, tid):
        return None


def _spx_opt(id_: str, action: str, d: date, qty: float, proceeds) -> Trade:
    return Trade(
        id=id_,
        date=d,
        account="schwab/personal",
        ticker="SPX",
        action=action,
        quantity=qty,
        proceeds=float(proceeds),
        cost_basis=0.0,
        option_details=OptionDetails(strike=4500, expiry=date(2025, 12, 19), call_put="C"),
        is_section_1256=True,
    )


def test_explain_exempt_section_1256_basic():
    loss = _spx_opt("1", "Sell", date(2024, 9, 15), 1, 100)
    buy = _spx_opt("2", "Buy", date(2024, 9, 22), 1, 100)
    repo = _FakeRepo([loss, buy])
    em = ExemptMatchRow(
        id=1,
        loss_trade_id=1,
        triggering_buy_id=2,
        exempt_reason="section_1256",
        rule_citation="IRC §1256(c)",
        notional_disallowed=Decimal("621.50"),
        confidence="Confirmed",
        matched_quantity=1.0,
        loss_account="schwab/personal",
        buy_account="schwab/personal",
        loss_sale_date="2024-09-15",
        triggering_buy_date="2024-09-22",
        ticker="SPX",
    )
    e = explain_exempt(em, repo=repo)
    assert isinstance(e, ExplanationModel)
    assert e.is_exempt is True
    assert e.rule_citation == "IRC §1256(c)"
    assert e.adjusted_basis_target is None
    assert "exempt" in e.summary.lower() or "§1256" in e.summary
    assert e.disallowed_or_notional == Decimal("621.50")


def test_explain_exempt_summary_mentions_index_options():
    loss = _spx_opt("3", "Sell", date(2024, 9, 15), 1, 100)
    buy = _spx_opt("4", "Buy", date(2024, 9, 22), 1, 100)
    repo = _FakeRepo([loss, buy])
    em = ExemptMatchRow(
        id=2,
        loss_trade_id=3,
        triggering_buy_id=4,
        exempt_reason="section_1256",
        rule_citation="IRC §1256(c)",
        notional_disallowed=Decimal("100"),
        confidence="Confirmed",
        matched_quantity=1.0,
        loss_account="x",
        buy_account="x",
        loss_sale_date="2024-09-15",
        triggering_buy_date="2024-09-22",
        ticker="SPX",
    )
    e = explain_exempt(em, repo=repo)
    assert "SPX" in e.summary or "index" in e.summary.lower()
