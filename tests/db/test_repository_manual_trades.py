from __future__ import annotations

from datetime import date

from sqlalchemy import text

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.models.domain import Trade


def _setup(tmp_path):
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    init_db(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO accounts(broker, label) VALUES ('Schwab','Tax')"))
    return Repository(engine)


def test_create_manual_trade_persists_and_marks_is_manual(tmp_path):
    repo = _setup(tmp_path)
    t = Trade(
        account="Schwab/Tax",
        date=date(2026, 1, 15),
        ticker="AAPL",
        action="Buy",
        quantity=10,
        cost_basis=1500.0,
        basis_source="user",
        is_manual=True,
    )
    saved = repo.create_manual_trade(t, etf_pairs={})
    assert saved.id is not None
    assert saved.is_manual is True
    assert saved.basis_source == "user"
    trades = repo.all_trades()
    assert len(trades) == 1
    assert trades[0].is_manual is True


def test_create_manual_trade_uses_manual_namespace_natural_key(tmp_path):
    repo = _setup(tmp_path)
    t = Trade(
        account="Schwab/Tax",
        date=date(2026, 1, 15),
        ticker="AAPL",
        action="Buy",
        quantity=10,
        cost_basis=1500.0,
        basis_source="user",
        is_manual=True,
    )
    repo.create_manual_trade(t, etf_pairs={})
    with repo.engine.begin() as conn:
        row = conn.execute(text("SELECT natural_key FROM trades")).first()
    assert row[0].startswith("manual:")
