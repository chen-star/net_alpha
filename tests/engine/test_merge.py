from __future__ import annotations

from datetime import date

import pytest

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
    explicitly cleared. Schwab is authoritative for lots it reports, so
    the engine's contradicting verdict is dropped entirely."""
    schwab_lots = [_gl(wash=False)]
    engine_violations = [
        _v(ticker="WRD", loss_date=(2026, 4, 20), account="schwab/personal", buy_account="schwab/personal"),
    ]
    merged = merge_violations(
        engine_violations=engine_violations,
        gl_lots_by_account={1: schwab_lots},
    )
    assert merged == []


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
    account. The matcher already labels ETF-pair triggers Unclear, and the
    merge keeps them for review since Schwab's same-ticker WS=No row only
    addresses the literal SPY-with-SPY scenario."""
    schwab_lots = [_gl(symbol="SPY", wash=False)]
    engine_violations = [
        _v(
            ticker="SPY",
            loss_date=(2026, 4, 20),
            account="schwab/personal",
            buy_account="schwab/personal",
            confidence="Unclear",
        ),
    ]
    merged = merge_violations(
        engine_violations=engine_violations,
        gl_lots_by_account={1: schwab_lots},
        substitute_tickers={"SPY": ["VOO", "IVV"]},
        replacement_tickers={"v1": "VOO"},
    )
    assert len(merged) == 1
    assert merged[0].source == "engine"
    assert merged[0].confidence == "Unclear"


def test_schwab_no_drops_engine_unclear_only_when_substitute_was_trigger():
    """Regression: a same-ticker engine violation that originally was Probable
    (e.g. options on different strikes) gets dropped when Schwab clears the
    matching G/L lot. Only Unclear (substitute) survives."""
    schwab_lots = [_gl(symbol="SPXW", wash=False)]
    engine_violations = [
        _v(
            ticker="SPXW",
            loss_date=(2026, 4, 20),
            account="schwab/personal",
            buy_account="schwab/personal",
            confidence="Probable",
        ),
    ]
    merged = merge_violations(
        engine_violations=engine_violations,
        gl_lots_by_account={1: schwab_lots},
    )
    assert merged == []


def test_schwab_violation_persists_via_repository(tmp_path):
    """End-to-end: merge_violations output for a Schwab Yes lot persists
    to DB when a matching Sell trade exists."""
    from datetime import datetime

    from net_alpha.db.connection import get_engine, init_db
    from net_alpha.db.repository import Repository
    from net_alpha.models.domain import ImportRecord, Trade

    engine = get_engine(tmp_path / "merge.db")
    init_db(engine)
    repo = Repository(engine)
    acct = repo.get_or_create_account("schwab", "personal")
    rec = ImportRecord(
        account_id=acct.id,
        csv_filename="t.csv",
        csv_sha256="abc",
        imported_at=datetime(2026, 4, 25),
        trade_count=1,
    )
    repo.add_import(
        acct,
        rec,
        [
            Trade(
                account=acct.display(),
                date=date(2026, 4, 20),
                ticker="WRD",
                action="Sell",
                quantity=100,
                proceeds=824.96,
                cost_basis=900.0,
            ),
        ],
    )
    schwab_lots = [_gl(wash=True, disallowed=130.33)]
    merged = merge_violations(
        engine_violations=[],
        gl_lots_by_account={acct.id: schwab_lots},
    )
    repo.replace_violations_in_window(date(2026, 3, 20), date(2026, 5, 20), merged)
    persisted = repo.all_violations()
    assert len(persisted) == 1
    assert persisted[0].source == "schwab_g_l"
    assert persisted[0].confidence == "Confirmed"
    assert persisted[0].disallowed_loss == pytest.approx(130.33)


def test_schwab_violation_silently_dropped_when_no_matching_sell(tmp_path):
    """If a Schwab G/L wash sale row has no matching Sell trade in our DB
    (e.g., G/L imported without Transaction History), the violation is
    silently dropped during persistence rather than crashing."""
    from net_alpha.db.connection import get_engine, init_db
    from net_alpha.db.repository import Repository

    engine = get_engine(tmp_path / "merge_drop.db")
    init_db(engine)
    repo = Repository(engine)
    acct = repo.get_or_create_account("schwab", "personal")
    schwab_lots = [_gl(wash=True, disallowed=130.33)]
    merged = merge_violations(
        engine_violations=[],
        gl_lots_by_account={acct.id: schwab_lots},
    )
    # No Sell trade exists for WRD — should not crash
    repo.replace_violations_in_window(date(2026, 3, 20), date(2026, 5, 20), merged)
    assert len(repo.all_violations()) == 0
