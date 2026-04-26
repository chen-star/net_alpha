from __future__ import annotations

from datetime import date, datetime

import pytest

from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.engine.stitch import match_symbol, stitch_account
from net_alpha.models.domain import (
    Account,
    ImportRecord,
    OptionDetails,
    Trade,
)
from net_alpha.models.realized_gl import RealizedGLLot


@pytest.fixture
def repo(tmp_path):
    engine = get_engine(tmp_path / "stitch.db")
    init_db(engine)
    return Repository(engine)


def _stock_trade(date_, ticker, action, qty, *, proceeds=None, cost_basis=None):
    return Trade(
        account="schwab/personal",
        date=date_,
        ticker=ticker,
        action=action,
        quantity=qty,
        proceeds=proceeds,
        cost_basis=cost_basis,
    )


def _option_trade(date_, ticker, strike, expiry_iso, cp, action, qty, *, proceeds=None):
    return Trade(
        account="schwab/personal",
        date=date_,
        ticker=ticker,
        action=action,
        quantity=qty,
        proceeds=proceeds,
        option_details=OptionDetails(strike=strike, expiry=date.fromisoformat(expiry_iso), call_put=cp),
    )


def _import(repo: Repository, acct: Account, trades: list[Trade]) -> int:
    rec = ImportRecord(
        account_id=acct.id,
        csv_filename="t.csv",
        csv_sha256="abc",
        imported_at=datetime(2026, 4, 25),
        trade_count=len(trades),
    )
    return repo.add_import(acct, rec, trades).import_id


def test_match_symbol_stock_returns_ticker():
    t = _stock_trade(date(2026, 4, 20), "WRD", "Sell", 100, proceeds=824.96)
    assert match_symbol(t) == "WRD"


def test_match_symbol_option_returns_schwab_format():
    t = _option_trade(date(2026, 4, 20), "CRCL", 150.00, "2026-06-18", "C", "Sell", 1, proceeds=330.33)
    assert match_symbol(t) == "CRCL 06/18/2026 150.00 C"


def test_stitch_hydrates_sell_from_gl_when_match_exists(repo):
    acct = repo.get_or_create_account("schwab", "personal")
    sell = _stock_trade(date(2026, 4, 20), "WRD", "Sell", 100, proceeds=824.96)
    import_id = _import(repo, acct, [sell])
    repo.add_gl_lots(
        acct,
        import_id,
        [
            RealizedGLLot(
                account_display=acct.display(),
                symbol_raw="WRD",
                ticker="WRD",
                closed_date=date(2026, 4, 20),
                opened_date=date(2026, 2, 11),
                quantity=100.0,
                proceeds=824.96,
                cost_basis=800.66,
                unadjusted_cost_basis=800.66,
                wash_sale=False,
                disallowed_loss=0.0,
                term="Short Term",
            ),
        ],
    )
    summary = stitch_account(repo, acct.id)
    assert summary.from_gl == 1
    sells = repo.get_sells_for_account(acct.id)
    assert sells[0].cost_basis == pytest.approx(800.66)


def test_stitch_falls_back_to_fifo_when_no_gl(repo):
    acct = repo.get_or_create_account("schwab", "personal")
    trades = [
        _stock_trade(date(2026, 3, 10), "AAPL", "Buy", 5, cost_basis=500.0),
        _stock_trade(date(2026, 3, 15), "AAPL", "Buy", 10, cost_basis=1100.0),
        _stock_trade(date(2026, 4, 20), "AAPL", "Sell", 8, proceeds=720.0),
    ]
    _import(repo, acct, trades)
    summary = stitch_account(repo, acct.id)
    assert summary.from_fifo == 1
    sells = repo.get_sells_for_account(acct.id)
    sell = sells[0]
    # Consumed: 5 from $500 lot ($100/sh) + 3 from $110/sh lot = 500 + 330 = 830
    assert sell.cost_basis == pytest.approx(830.0)
    assert sell.basis_source == "fifo"


def test_stitch_marks_unknown_when_no_gl_and_no_buys(repo):
    acct = repo.get_or_create_account("schwab", "personal")
    sell = _stock_trade(date(2026, 4, 20), "AAPL", "Sell", 1, proceeds=100.0)
    _import(repo, acct, [sell])
    summary = stitch_account(repo, acct.id)
    assert summary.unknown == 1
    sells = repo.get_sells_for_account(acct.id)
    assert sells[0].cost_basis is None
    assert sells[0].basis_source == "unknown"


def test_stitch_aggregates_multiple_gl_lots_for_one_sell(repo):
    acct = repo.get_or_create_account("schwab", "personal")
    sell = _stock_trade(date(2026, 4, 20), "WRD", "Sell", 100, proceeds=824.96)
    import_id = _import(repo, acct, [sell])
    repo.add_gl_lots(
        acct,
        import_id,
        [
            RealizedGLLot(
                account_display=acct.display(),
                symbol_raw="WRD",
                ticker="WRD",
                closed_date=date(2026, 4, 20),
                opened_date=date(2026, 1, 1),
                quantity=40.0,
                proceeds=329.99,
                cost_basis=320.00,
                unadjusted_cost_basis=320.00,
                wash_sale=False,
                disallowed_loss=0.0,
                term="Short Term",
            ),
            RealizedGLLot(
                account_display=acct.display(),
                symbol_raw="WRD",
                ticker="WRD",
                closed_date=date(2026, 4, 20),
                opened_date=date(2026, 2, 11),
                quantity=60.0,
                proceeds=494.97,
                cost_basis=480.66,
                unadjusted_cost_basis=480.66,
                wash_sale=False,
                disallowed_loss=0.0,
                term="Short Term",
            ),
        ],
    )
    stitch_account(repo, acct.id)
    sells = repo.get_sells_for_account(acct.id)
    assert sells[0].cost_basis == pytest.approx(800.66)


def test_stitch_handles_quantity_mismatch_within_tolerance(repo):
    acct = repo.get_or_create_account("schwab", "personal")
    sell = _stock_trade(date(2026, 4, 20), "WRD", "Sell", 100, proceeds=824.96)
    import_id = _import(repo, acct, [sell])
    repo.add_gl_lots(
        acct,
        import_id,
        [
            RealizedGLLot(
                account_display=acct.display(),
                symbol_raw="WRD",
                ticker="WRD",
                closed_date=date(2026, 4, 20),
                opened_date=date(2026, 2, 11),
                quantity=99.7,
                proceeds=823.0,
                cost_basis=798.0,
                unadjusted_cost_basis=798.0,
                wash_sale=False,
                disallowed_loss=0.0,
                term="Short Term",
            ),
        ],
    )
    summary = stitch_account(repo, acct.id)
    assert summary.from_gl == 1
    assert summary.warnings == []
    sells = repo.get_sells_for_account(acct.id)
    assert sells[0].cost_basis == pytest.approx(798.0)


def test_stitch_records_warning_on_quantity_mismatch_outside_tolerance(repo):
    acct = repo.get_or_create_account("schwab", "personal")
    sell = _stock_trade(date(2026, 4, 20), "WRD", "Sell", 100, proceeds=824.96)
    import_id = _import(repo, acct, [sell])
    repo.add_gl_lots(
        acct,
        import_id,
        [
            RealizedGLLot(
                account_display=acct.display(),
                symbol_raw="WRD",
                ticker="WRD",
                closed_date=date(2026, 4, 20),
                opened_date=date(2026, 2, 11),
                quantity=50.0,
                proceeds=400.0,
                cost_basis=380.0,
                unadjusted_cost_basis=380.0,
                wash_sale=False,
                disallowed_loss=0.0,
                term="Short Term",
            ),
        ],
    )
    summary = stitch_account(repo, acct.id)
    assert summary.from_gl == 1
    assert len(summary.warnings) == 1
    assert "WRD" in summary.warnings[0]


def test_stitch_re_runs_idempotent(repo):
    """Running stitch twice in a row produces the same result."""
    acct = repo.get_or_create_account("schwab", "personal")
    sell = _stock_trade(date(2026, 4, 20), "WRD", "Sell", 100, proceeds=824.96)
    import_id = _import(repo, acct, [sell])
    repo.add_gl_lots(
        acct,
        import_id,
        [
            RealizedGLLot(
                account_display=acct.display(),
                symbol_raw="WRD",
                ticker="WRD",
                closed_date=date(2026, 4, 20),
                opened_date=date(2026, 2, 11),
                quantity=100.0,
                proceeds=824.96,
                cost_basis=800.66,
                unadjusted_cost_basis=800.66,
                wash_sale=False,
                disallowed_loss=0.0,
                term="Short Term",
            ),
        ],
    )
    s1 = stitch_account(repo, acct.id)
    s2 = stitch_account(repo, acct.id)
    assert s1.from_gl == s2.from_gl == 1
