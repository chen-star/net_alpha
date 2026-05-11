"""End-to-end recompute test exercising §1256 MTM (Task 6)."""

from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlmodel import Session, SQLModel, create_engine

import net_alpha.db.tables  # noqa: F401 — register SQLModel metadata
from net_alpha.db.migrations import migrate
from net_alpha.db.repository import Repository
from net_alpha.models.domain import ImportRecord, OptionDetails, Trade
from net_alpha.portfolio.after_tax import Period


@pytest.fixture()
def repo(tmp_path):
    """Migrated SQLite repo backed by a per-test temp file."""
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        migrate(session)
    return Repository(engine)


def _seed_import(repo: Repository, trades: list[Trade]) -> None:
    """Create account 'test/personal' and add trades via add_import."""
    account = repo.get_or_create_account(broker="test", label="personal")
    record = ImportRecord(
        account_id=account.id,
        csv_filename="test.csv",
        csv_sha256="sha-test",
        imported_at=datetime.now(),
        trade_count=len(trades),
    )
    repo.add_import(account, record, trades)


def _fake_fmv_fn_factory(price_map):
    """Build an fmv_fn that looks up (ticker, strike, expiry, cp, year) in `price_map`."""

    def fn(ticker, opt, year):
        return price_map.get(
            (ticker, opt.strike, opt.expiry.isoformat(), opt.call_put, year),
            (None, "missing"),
        )

    return fn


def test_recompute_writes_mtm_rows_for_each_open_year(repo, monkeypatch):
    """SPX long call bought 2024-03-01, never sold — MTM row for 2024 AND 2025."""
    import net_alpha.engine.recompute as rc_mod

    o = OptionDetails(strike=4000.0, expiry=date(2026, 6, 19), call_put="C")
    buy = Trade(
        account="test/personal",
        date=date(2024, 3, 1),
        ticker="SPX",
        action="Buy",
        quantity=1,
        proceeds=None,
        cost_basis=100,
        option_details=o,
        is_section_1256=True,
    )
    _seed_import(repo, [buy])

    price_map = {
        ("SPX", 4000.0, "2026-06-19", "C", 2024): (Decimal("150"), "yahoo_close"),
        ("SPX", 4000.0, "2026-06-19", "C", 2025): (Decimal("180"), "yahoo_close"),
    }
    monkeypatch.setattr(rc_mod, "_fmv_fn_for_recompute", lambda _repo: _fake_fmv_fn_factory(price_map))

    # Pin "today" so the open-year range is deterministic.
    import datetime as _dt

    class _FixedDate(_dt.date):
        @classmethod
        def today(cls):
            return _dt.date(2025, 6, 1)

    monkeypatch.setattr(rc_mod, "date", _FixedDate)

    rc_mod.recompute_all_violations(repo, {})

    rows_2024 = repo.section_1256_mtm_rows(Period.for_year(2024), account=None)
    rows_2025 = repo.section_1256_mtm_rows(Period.for_year(2025), account=None)
    assert len(rows_2024) == 1
    assert rows_2024[0].fmv == Decimal("150")
    assert rows_2024[0].basis_before == Decimal("100")
    assert rows_2024[0].unrealized_pnl == Decimal("50.00")
    assert len(rows_2025) == 1
    assert rows_2025[0].fmv == Decimal("180")
    assert rows_2025[0].basis_before == Decimal("150")  # chained from prior MTM
    assert rows_2025[0].unrealized_pnl == Decimal("30.00")


def test_recompute_classifier_uses_prior_mtm_for_next_year_sell(repo, monkeypatch):
    """Buy 2024, MTM at 2024-end = 150, Sell in 2025 @ 180 — realized = 30 (not 80)."""
    import net_alpha.engine.recompute as rc_mod

    o = OptionDetails(strike=4000.0, expiry=date(2026, 6, 19), call_put="C")
    buy = Trade(
        account="test/personal",
        date=date(2024, 3, 1),
        ticker="SPX",
        action="Buy",
        quantity=1,
        proceeds=None,
        cost_basis=100,
        option_details=o,
        is_section_1256=True,
    )
    sell = Trade(
        account="test/personal",
        date=date(2025, 5, 1),
        ticker="SPX",
        action="Sell",
        quantity=1,
        proceeds=180,
        cost_basis=None,
        option_details=o,
        is_section_1256=True,
    )
    _seed_import(repo, [buy, sell])

    price_map = {
        ("SPX", 4000.0, "2026-06-19", "C", 2024): (Decimal("150"), "yahoo_close"),
    }
    monkeypatch.setattr(rc_mod, "_fmv_fn_for_recompute", lambda _repo: _fake_fmv_fn_factory(price_map))

    import datetime as _dt

    class _FixedDate(_dt.date):
        @classmethod
        def today(cls):
            return _dt.date(2026, 1, 1)

    monkeypatch.setattr(rc_mod, "date", _FixedDate)

    rc_mod.recompute_all_violations(repo, {})

    classifications = repo.list_section_1256_classifications(year=2025)
    assert len(classifications) == 1
    # realized = 180 (proceeds) - 150 (prior-year MTM basis) = 30
    assert classifications[0].realized_pnl == Decimal("30")
    assert classifications[0].long_term_portion == Decimal("18.00")
    assert classifications[0].short_term_portion == Decimal("12.00")
