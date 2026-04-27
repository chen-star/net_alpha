"""Shared fixtures for all integration tests."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml
from sqlmodel import Session, SQLModel

from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.models.domain import Account, ImportRecord, Trade

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
FIXTURES_DIR = Path(__file__).parents[1] / "fixtures"
PROJECT_ROOT = Path(__file__).parents[2]


@pytest.fixture
def schwab_csv() -> Path:
    return FIXTURES_DIR / "schwab_sample.csv"


@pytest.fixture
def robinhood_csv() -> Path:
    return FIXTURES_DIR / "robinhood_sample.csv"


@pytest.fixture
def etf_pairs() -> dict[str, list[str]]:
    with open(PROJECT_ROOT / "etf_pairs.yaml") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
@pytest.fixture
def temp_db(tmp_path):
    """Fresh isolated SQLite DB. Yields (engine, session, db_path)."""
    db_path = tmp_path / "test.db"
    engine = get_engine(db_path)
    init_db(engine)
    with Session(engine) as session:
        yield engine, session, db_path


# ---------------------------------------------------------------------------
# LLM mapping constants
# ---------------------------------------------------------------------------
SCHWAB_MAPPING = {
    "date": "Date",
    "ticker": "Symbol",
    "action": "Action",
    "quantity": "Quantity",
    "proceeds": "Amount",
    "cost_basis": "Cost Basis",
    "buy_values": ["Buy", "Reinvest"],
    "sell_values": ["Sell"],
    "option_format": "schwab_human",
}

ROBINHOOD_MAPPING = {
    "date": "Activity Date",
    "ticker": "Instrument",
    "action": "Trans Code",
    "quantity": "Quantity",
    "proceeds": "Amount",
    "cost_basis": None,
    "buy_values": ["Buy"],
    "sell_values": ["Sell"],
    "option_format": "robinhood_human",
}


def make_llm_response(mapping_dict: dict) -> MagicMock:
    """Build a mock Anthropic API response containing SchemaMapping JSON."""
    resp = MagicMock()
    resp.content = [MagicMock(text=json.dumps(mapping_dict))]
    return resp


# ---------------------------------------------------------------------------
# LLM mock (engine-tier tests: pass mock_client directly into ImportContext)
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_anthropic_client() -> MagicMock:
    """
    A bare MagicMock Anthropic client for use in engine-tier tests.
    Set .messages.create.return_value = make_llm_response(MAPPING) before use.
    Does NOT patch any module — callers pass this directly into ImportContext.
    """
    return MagicMock()


# ---------------------------------------------------------------------------
# Minimal repo + builders fixtures (mirroring tests/splits/conftest.py pattern)
# ---------------------------------------------------------------------------


@pytest.fixture
def repo(tmp_path: Path) -> Repository:
    """Fresh isolated SQLite DB for split autosync integration tests."""
    db_path = tmp_path / "autosync_test.db"
    eng = get_engine(db_path)
    SQLModel.metadata.create_all(eng)
    return Repository(eng)


def _make_buy(
    account_display: str,
    ticker: str,
    day: date,
    qty: float = 10.0,
    cost: float = 1800.0,
) -> Trade:
    return Trade(
        account=account_display,
        date=day,
        ticker=ticker,
        action="Buy",
        quantity=qty,
        proceeds=None,
        cost_basis=cost,
    )


def _seed_import(
    repo: Repository,
    broker: str,
    label: str,
    trades: list[Trade],
    csv_filename: str = "seed.csv",
) -> tuple[Account, int]:
    account = repo.get_or_create_account(broker, label)
    record = ImportRecord(
        account_id=account.id,
        csv_filename=csv_filename,
        csv_sha256=f"sha-{csv_filename}",
        imported_at=datetime.now(),
        trade_count=len(trades),
    )
    result = repo.add_import(account, record, trades)
    return account, result.import_id


@pytest.fixture
def builders():
    """Expose builder functions to integration tests via a single fixture."""
    return type(
        "B",
        (),
        {
            "make_buy": staticmethod(_make_buy),
            "seed_import": staticmethod(_seed_import),
        },
    )
