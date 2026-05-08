from __future__ import annotations

from pathlib import Path

import pytest

from net_alpha.db.connection import get_engine
from net_alpha.db.repository import Repository
from net_alpha.web.demo.data import DEMO_IRA, DEMO_TAXABLE
from net_alpha.web.demo.fixture import build_demo_db


def test_demo_taxable_has_expected_row_count() -> None:
    assert len(DEMO_TAXABLE) >= 18


def test_demo_ira_has_expected_row_count() -> None:
    assert len(DEMO_IRA) >= 8


def test_demo_rows_use_required_schwab_columns() -> None:
    required = {"Date", "Action", "Symbol", "Quantity", "Price", "Amount"}
    for row in DEMO_TAXABLE + DEMO_IRA:
        assert required <= row.keys(), f"missing columns in row {row}"


def test_demo_taxable_includes_tsla_wash_sale_round_trip() -> None:
    """Confirmed wash sale: Buy TSLA, sell at loss, rebuy within 30 days."""
    tsla_actions = [r for r in DEMO_TAXABLE if r["Symbol"] == "TSLA"]
    actions = [r["Action"] for r in tsla_actions]
    assert actions.count("Buy") >= 2
    assert actions.count("Sell") >= 1


def test_demo_includes_section_1256_spx() -> None:
    rows = DEMO_TAXABLE + DEMO_IRA
    assert any(r["Symbol"].startswith("SPX") for r in rows)


def test_demo_includes_options() -> None:
    rows = DEMO_TAXABLE + DEMO_IRA
    option_rows = [r for r in rows if r["Action"] in {"Buy to Open", "Sell to Close", "Sell to Open", "Buy to Close"}]
    assert len(option_rows) >= 6


@pytest.fixture()
def demo_db(tmp_path: Path) -> Path:
    target = tmp_path / "demo.db"
    build_demo_db(target)
    return target


def test_build_demo_db_creates_two_accounts(demo_db: Path) -> None:
    repo = Repository(get_engine(demo_db))
    accounts = repo.list_accounts()
    labels = {a.label for a in accounts}
    assert labels == {"taxable", "ira"}


def test_build_demo_db_imports_expected_trade_count(demo_db: Path) -> None:
    repo = Repository(get_engine(demo_db))
    trades = repo.all_trades()
    assert len(trades) >= 26


def test_build_demo_db_detects_wash_sales(demo_db: Path) -> None:
    repo = Repository(get_engine(demo_db))
    violations = repo.all_violations()
    assert len(violations) >= 2


def test_build_demo_db_idempotent(tmp_path: Path) -> None:
    target = tmp_path / "demo.db"
    build_demo_db(target)
    first_count = len(Repository(get_engine(target)).all_trades())
    build_demo_db(target)
    second_count = len(Repository(get_engine(target)).all_trades())
    assert first_count == second_count
