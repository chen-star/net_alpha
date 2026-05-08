"""Wash-sales filter collapsible behavior."""

import pathlib
import tempfile
from datetime import date, datetime

from fastapi.testclient import TestClient

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.models.domain import ImportRecord, Trade
from net_alpha.web.app import create_app


def _client():
    d = tempfile.mkdtemp()
    s = Settings(data_dir=pathlib.Path(d))
    # Seed a no-violation import so the page-level empty hero on /tax does
    # not suppress the wash-sales tab body these tests assert on.
    engine = get_engine(s.db_path)
    init_db(engine)
    repo = Repository(engine)
    acct = repo.get_or_create_account("schwab", "personal")
    repo.add_import(
        acct,
        ImportRecord(
            account_id=acct.id,
            csv_filename="seed.csv",
            csv_sha256="sha-seed",
            imported_at=datetime.now(),
            trade_count=1,
        ),
        [
            Trade(
                account=acct.display(),
                date=date(2024, 5, 1),
                ticker="AAPL",
                action="Buy",
                quantity=10.0,
                proceeds=None,
                cost_basis=1700.0,
            )
        ],
    )
    app = create_app(s)
    return TestClient(app)


def test_filter_collapsed_with_no_query():
    with _client() as c:
        r = c.get("/wash-sales")
    html = r.text
    idx = html.find("<details")
    assert idx != -1, "expected a <details> wrapping the filter"
    end = html.find(">", idx)
    open_tag = html[idx:end]
    assert "open" not in open_tag, f"filter should be collapsed by default; got {open_tag!r}"


def test_filter_open_when_ticker_param_set():
    with _client() as c:
        r = c.get("/wash-sales?ticker=TSLA")
    html = r.text
    idx = html.find("<details")
    assert idx != -1
    end = html.find(">", idx)
    open_tag = html[idx:end]
    assert "open" in open_tag, f"filter should be expanded when a filter is active; got {open_tag!r}"


def test_tax_wash_tab_shows_explanatory_header():
    with _client() as c:
        r = c.get("/tax?view=wash-sales")
    assert r.status_code == 200
    text = r.text
    # The Watch label is inside a <span>, so match on the text that follows.
    assert ("— open positions where you closed a loss recently" in text) or (
        "&mdash; open positions where you closed a loss recently" in text
    ), "explainer header missing"
