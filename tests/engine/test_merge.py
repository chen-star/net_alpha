from __future__ import annotations

from datetime import date

from net_alpha.engine.merge import merge_violations
from net_alpha.models.domain import WashSaleViolation
from net_alpha.models.realized_gl import RealizedGLLot


def _gl(symbol="WRD", closed=(2026, 4, 20), opened=(2026, 2, 11), wash=False, disallowed=0.0):
    return RealizedGLLot(
        account_display="schwab/personal",
        symbol_raw=symbol,
        ticker=symbol.split()[0],
        closed_date=date(*closed),
        opened_date=date(*opened),
        quantity=1.0,
        proceeds=10.0,
        cost_basis=20.0,
        unadjusted_cost_basis=20.0,
        wash_sale=wash,
        disallowed_loss=disallowed,
        term="Short Term",
    )


def _v(
    ticker="WRD",
    loss_date=(2026, 4, 20),
    buy_date=(2026, 4, 25),
    account="schwab/personal",
    buy_account=None,
    loss=10.0,
    qty=1.0,
    confidence="Confirmed",
):
    return WashSaleViolation(
        loss_trade_id="t1",
        replacement_trade_id="t2",
        confidence=confidence,
        disallowed_loss=loss,
        matched_quantity=qty,
        loss_account=account,
        buy_account=buy_account or account,
        loss_sale_date=date(*loss_date),
        triggering_buy_date=date(*buy_date),
        ticker=ticker,
    )


def test_schwab_yes_creates_confirmed_violation():
    """A Schwab G/L row flagged Wash Sale=Yes becomes a Confirmed violation
    sourced from Schwab even if the engine missed it."""
    schwab_lots = [_gl(wash=True, disallowed=130.33)]
    engine_violations: list[WashSaleViolation] = []
    merged = merge_violations(
        engine_violations=engine_violations,
        gl_lots_by_account={1: schwab_lots},
    )
    assert len(merged) == 1
    assert merged[0].source == "schwab_g_l"
    assert merged[0].confidence == "Confirmed"
    assert merged[0].disallowed_loss == 130.33


def test_schwab_no_suppresses_engine_same_account_exact_ticker():
    """Engine flags a same-account exact-ticker wash sale that Schwab
    explicitly cleared. Engine's verdict is downgraded to Unclear."""
    schwab_lots = [_gl(wash=False)]
    engine_violations = [
        _v(ticker="WRD", loss_date=(2026, 4, 20), account="schwab/personal", buy_account="schwab/personal"),
    ]
    merged = merge_violations(
        engine_violations=engine_violations,
        gl_lots_by_account={1: schwab_lots},
    )
    assert len(merged) == 1
    assert merged[0].source == "engine"
    assert merged[0].confidence == "Unclear"


def test_engine_flag_dedupes_with_matching_schwab_yes():
    """Both engine and Schwab flagged the same wash sale — only Schwab's row survives."""
    schwab_lots = [_gl(wash=True, disallowed=130.33)]
    engine_violations = [
        _v(ticker="WRD", loss_date=(2026, 4, 20), account="schwab/personal", buy_account="schwab/personal"),
    ]
    merged = merge_violations(
        engine_violations=engine_violations,
        gl_lots_by_account={1: schwab_lots},
    )
    assert len(merged) == 1
    assert merged[0].source == "schwab_g_l"


def test_engine_cross_account_wash_sale_kept_as_probable():
    """Engine flags a wash sale where the buy is in a DIFFERENT account.
    Schwab can't see other brokers, so the engine keeps the verdict."""
    schwab_lots = [_gl(wash=False)]
    engine_violations = [
        _v(
            ticker="WRD",
            loss_date=(2026, 4, 20),
            account="schwab/personal",
            buy_account="fidelity/joint",
            confidence="Probable",
        ),
    ]
    merged = merge_violations(
        engine_violations=engine_violations,
        gl_lots_by_account={1: schwab_lots},
    )
    assert len(merged) == 1
    assert merged[0].source == "engine"
    assert merged[0].confidence == "Probable"


def test_no_gl_for_account_keeps_engine_violations_unchanged():
    """When an account has no G/L coverage, engine output is preserved verbatim."""
    engine_violations = [
        _v(ticker="WRD", confidence="Probable"),
    ]
    merged = merge_violations(
        engine_violations=engine_violations,
        gl_lots_by_account={},  # no G/L data for any account
    )
    assert len(merged) == 1
    assert merged[0].source == "engine"
    assert merged[0].confidence == "Probable"


def test_substantially_identical_engine_detection_marked_unclear():
    """Engine flags an ETF-pair (e.g. SPY loss + VOO buy) within the Schwab
    account. Schwab's G/L doesn't have a 'wash sale' row for the SPY ticker.
    Surface as Unclear since Schwab doesn't model substitutes."""
    schwab_lots = [_gl(symbol="SPY", wash=False)]
    engine_violations = [
        _v(
            ticker="SPY",
            loss_date=(2026, 4, 20),
            account="schwab/personal",
            buy_account="schwab/personal",
            confidence="Probable",
        ),
    ]
    merged = merge_violations(
        engine_violations=engine_violations,
        gl_lots_by_account={1: schwab_lots},
        substitute_tickers={"SPY": ["VOO", "IVV"]},
        replacement_tickers={"v1": "VOO"},
    )
    # The engine's loss is on SPY but the replacement was VOO (different ticker)
    # — Schwab sees the SPY row as not-wash-sale, but our engine knows VOO is
    # substantially identical. Mark as Unclear to surface for review.
    assert len(merged) == 1
    assert merged[0].source == "engine"
    assert merged[0].confidence == "Unclear"
