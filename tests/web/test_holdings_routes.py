from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import text

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine
from net_alpha.web.app import create_app


def _client(tmp_path):
    return TestClient(create_app(Settings(data_dir=tmp_path)))


def _seed_import(tmp_path) -> None:
    """Insert one stub import so the page renders with data."""
    settings = Settings(data_dir=tmp_path)
    engine = get_engine(settings.db_path)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO accounts(broker, label) VALUES ('Schwab', 'Tax')"))
        conn.execute(
            text(
                "INSERT INTO imports(account_id, csv_filename, csv_sha256, imported_at, trade_count) "
                "VALUES (1, 'x.csv', 'h', '2026-04-26T00:00:00', 0)"
            )
        )


def test_holdings_page_returns_200(tmp_path):
    client = _client(tmp_path)  # creates app + initialises DB tables
    _seed_import(tmp_path)
    response = client.get("/holdings")
    assert response.status_code == 200
    # The page wires the existing positions fragment.
    assert "/portfolio/positions" in response.text
    assert 'id="holdings-positions"' in response.text


def test_holdings_page_active_in_nav(tmp_path):
    client = _client(tmp_path)
    response = client.get("/holdings")
    assert response.status_code == 200
    assert ">Holdings<" in response.text
    assert 'class="nav-link active"' in response.text


def test_holdings_link_appears_on_other_pages(tmp_path):
    client = _client(tmp_path)
    response = client.get("/")
    assert response.status_code == 200
    assert ">Holdings<" in response.text


def test_holdings_renders_symbol_multiselect_trigger(tmp_path):
    """The holdings positions fragment should expose a multi-select trigger."""
    client = _client(tmp_path)
    # Fragment endpoint renders the toolbar inline.
    r = client.get("/portfolio/positions?period=ytd")
    assert r.status_code == 200
    html = r.text
    # Trigger button is wired to the named Alpine component; label() is evaluated
    # client-side so "Symbols:" text is not in the server-rendered HTML.
    assert "symbolFilter(" in html
    # Alpine state hook for the popover.
    assert "x-data" in html
    # No native search input.
    assert 'name="q"' not in html


def test_holdings_symbol_filter_with_selection_in_url(tmp_path):
    """When ?symbols= is present, the trigger summarizes the selection."""
    client = _client(tmp_path)
    r = client.get("/portfolio/positions?period=ytd&symbols=AAPL,MSFT")
    assert r.status_code == 200
    html = r.text
    # The summary names the selected symbols.
    assert "AAPL" in html
    assert "MSFT" in html


def test_symbol_filter_universe_excludes_closed_when_show_open(client, builders, repo):
    """The Symbols dropdown universe should reflect the current Show mode.
    Show=Open must not list symbols whose lots have all been sold off."""
    from datetime import date

    from net_alpha.engine.recompute import recompute_all_violations
    from net_alpha.engine.stitch import stitch_account

    account, _ = builders.seed_import(
        repo,
        "schwab",
        "lt",
        [
            builders.make_buy("schwab/lt", "AAPL", date(2026, 1, 5)),
            # GPRO bought and fully sold — closed.
            builders.make_buy("schwab/lt", "GPRO", date(2026, 1, 5), qty=100, cost=300.0),
            builders.make_sell("schwab/lt", "GPRO", date(2026, 1, 6), qty=100, proceeds=350.0, cost=300.0),
        ],
    )
    stitch_account(repo, account.id)
    recompute_all_violations(repo, {})

    res_open = client.get("/portfolio/positions?period=ytd&show=open")
    assert res_open.status_code == 200
    # AAPL is open and must appear in the picker config; GPRO is closed and must not.
    assert "AAPL" in res_open.text
    # The picker config "all" list should not contain GPRO when showing only open.
    # GPRO appearing only inside the picker config JSON would still match a naive
    # substring check, so assert against the JSON shape directly.
    assert '"GPRO"' not in res_open.text

    res_all = client.get("/portfolio/positions?period=ytd&show=all")
    assert res_all.status_code == 200
    # In Show=All, GPRO is part of the universe (closed-in-period rows are included).
    assert "GPRO" in res_all.text


def test_holdings_table_targets_holdings_positions_wrapper(tmp_path):
    """Show/Pagesize/Pagination buttons must swap into #holdings-positions, not the legacy #portfolio-positions."""
    client = _client(tmp_path)
    r = client.get("/portfolio/positions?period=ytd")
    assert r.status_code == 200
    html = r.text
    # All hx-target attributes in the fragment should target #holdings-positions.
    assert 'hx-target="#holdings-positions"' in html
    assert 'hx-target="#portfolio-positions"' not in html


def test_holdings_status_hint_uses_ascii_quotes(tmp_path):
    """The status-hint span must not have Unicode smart quotes around its class attribute."""
    client = _client(tmp_path)
    r = client.get("/portfolio/positions?period=ytd")
    assert r.status_code == 200
    # Must not appear anywhere in the rendered HTML — those break the class parser.
    assert "“" not in r.text
    assert "”" not in r.text
