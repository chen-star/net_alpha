"""E2E: Flow & Clarity Pass — scroll preservation and keyboard nav.

These flows assert user-visible behaviors that pure-server template snapshots
cannot capture: scroll Y is preserved across HTMX swaps (Task 4 split the
summary tile so checkbox-toggle does an out-of-band swap of only the summary,
not the table), and arrow keys traverse rows in long tables (Task 6 added
`data-table-nav` + `table_nav.js`).

Fixtures
--------
The shared ``live_server_seeded`` fixture in ``tests/web/e2e/conftest.py``
boots the demo DB, which has open unrealized-loss positions but no cached
price quotes. The harvest queue requires current quotes to compute losses,
so this module builds its own ``live_server_harvest`` fixture that seeds
buys + matching price_cache rows, producing a populated harvest table.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import socket
import threading
import time
from collections.abc import Iterator
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
import uvicorn
from playwright.sync_api import Page

from net_alpha.config import Settings
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.engine.etf_pairs import load_etf_pairs
from net_alpha.engine.recompute import recompute_all_violations
from net_alpha.engine.stitch import stitch_account
from net_alpha.models.domain import ImportRecord, Trade
from net_alpha.models.preferences import AccountPreference
from net_alpha.pricing.cache import PriceCache
from net_alpha.pricing.provider import Quote
from net_alpha.web.app import create_app


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _seed_harvest_loss(
    repo: Repository,
    account_display: str,
    ticker: str,
    day: date,
    *,
    qty: float = 10.0,
    cost: float = 1800.0,
) -> None:
    """Seed a single open buy lot. Pair with a price_cache row at < cost/qty
    to produce an unrealized loss visible to ``compute_harvest_queue``."""
    broker, label = account_display.split("/", 1)
    account = repo.get_or_create_account(broker, label)
    trade = Trade(
        account=account_display,
        date=day,
        ticker=ticker,
        action="Buy",
        quantity=qty,
        proceeds=None,
        cost_basis=cost,
    )
    record = ImportRecord(
        account_id=account.id,
        csv_filename=f"e2e_{ticker}.csv",
        csv_sha256=hashlib.sha256(f"{ticker}-{day}".encode()).hexdigest(),
        imported_at=datetime.now(),
        trade_count=1,
    )
    repo.add_import(account, record, [trade])


@pytest.fixture(scope="module")
def harvest_data_dir(tmp_path_factory) -> Path:
    """Isolated data dir with enough harvest rows to fill a scrolling viewport.

    Seeds 8 distinct open-loss positions across one account, then writes a
    matching price_cache row at half cost per share so each lot shows an
    unrealized loss. Also suppresses the profile-picker modal so Playwright
    pointer events aren't intercepted.
    """
    data_dir = tmp_path_factory.mktemp("e2e_harvest")
    settings = Settings(data_dir=data_dir)

    engine = get_engine(settings.db_path)
    init_db(engine)
    repo = Repository(engine)

    today = date.today()
    buy_day = today - dt.timedelta(days=45)  # short-term, definitely past trade settlement
    symbols = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH"]
    qty = 10.0
    cost = 1800.0  # $180/share basis
    for sym in symbols:
        _seed_harvest_loss(
            repo,
            "schwab/lt",
            sym,
            buy_day,
            qty=qty,
            cost=cost,
        )

    # Build lot rows from the seeded trades. add_import only writes the
    # trade table; lots are materialized by the wash-sale engine's
    # detect_in_window pass (called via recompute_all_violations) which
    # also writes lot rows. stitch_account is run first to hydrate any
    # Sell cost-basis (no-op here since we only seeded Buys), mirroring the
    # production import path.
    for account in repo.list_accounts():
        stitch_account(repo, account.id)
    etf_pairs = load_etf_pairs(user_path=None)
    recompute_all_violations(repo, etf_pairs)

    # Seed current-price quotes well below basis so every lot is at a loss.
    cache = PriceCache(engine)
    now = datetime.now(dt.UTC)
    cache.put_many([Quote(symbol=sym, price=Decimal("90.00"), as_of=now, source="test") for sym in symbols])

    # Suppress first-visit profile picker — same trick as the shared conftest.
    accounts = repo.list_accounts()
    if accounts:
        repo.upsert_user_preference(
            AccountPreference(
                account_id=accounts[0].id,
                profile="active",
                density="comfortable",
                theme="system",
                updated_at=datetime.now(),
            )
        )
    return data_dir


@pytest.fixture(scope="module")
def live_server_harvest(harvest_data_dir: Path) -> Iterator[str]:
    """Boot the app against the harvest-seeded data dir; yield the base URL."""
    port = _free_port()
    settings = Settings(data_dir=harvest_data_dir)
    app = create_app(settings)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                break
        except OSError:
            time.sleep(0.1)
    else:
        server.should_exit = True
        raise RuntimeError("live_server_harvest did not start within 5 s")

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=2.0)


def _suppress_overlays(page: Page) -> None:
    """Force-hide overlays that may intercept pointer/keyboard events.

    Mirrors the workaround in ``test_multi_account_filter_e2e._ready``: the
    ⌘K palette can fail to initialize cleanly in headless Chromium and leaves
    its full-screen backdrop intercepting events.
    """
    page.evaluate(
        """
        () => {
            document.querySelectorAll('[role="dialog"][aria-label="Command palette"]').forEach(el => {
                el.style.display = 'none';
            });
            document.querySelectorAll('dialog[open]').forEach(d => d.close());
        }
        """
    )


@pytest.mark.e2e
def test_harvest_checkbox_preserves_scroll(page: Page, live_server_harvest: str) -> None:
    """Toggling a row checkbox does an outerHTML swap of ``#harvest-summary``
    only. The table region remains in place, so the page's scroll position
    must NOT jump."""
    # The user-facing entry to the harvest plan is /positions?view=at-loss,
    # which loads /tax/harvest/plan as an HTMX fragment into #harvest-queue-region.
    # Only the full page boots Alpine, htmx, and table_nav.js — the bare fragment
    # has no <script> tags, so navigating to it directly would leave keyboard
    # nav disabled and palette JS uninitialized.
    page.goto(f"{live_server_harvest}/positions?view=at-loss", wait_until="networkidle", timeout=15_000)
    _suppress_overlays(page)
    # Wait for the harvest summary panel; signals plan-builder rendered.
    page.wait_for_selector("#harvest-summary", timeout=5_000)

    # Confirm we have a populated table (at least one checkbox to click).
    checkbox_count = page.locator("#harvest-table input[type='checkbox'][name='pick']").count()
    assert checkbox_count > 0, (
        "harvest fixture did not produce any rows — check seed; "
        "without rows this test cannot exercise the scroll-preservation path"
    )

    # Scroll down inside the page; the harvest plan view has the queue,
    # caveat block, and summary stacked so 600px should be reachable.
    page.evaluate("window.scrollTo(0, 600)")
    page.wait_for_timeout(100)
    scroll_before = page.evaluate("window.scrollY")
    if scroll_before < 100:
        # Page content shorter than expected for this viewport; without
        # measurable scroll we can't distinguish "preserved" from "no-op".
        pytest.skip(f"page didn't scroll enough to test preservation (got {scroll_before}px)")

    # Toggle the first row checkbox; HTMX fires hx-get with hx-target=#harvest-summary.
    page.locator("#harvest-table input[type='checkbox'][name='pick']").first.check()
    # Allow HTMX request + outerHTML swap to settle.
    page.wait_for_timeout(800)

    scroll_after = page.evaluate("window.scrollY")
    # Allow 50px slop for browser-driven reflow.
    assert abs(scroll_after - scroll_before) < 50, (
        f"scroll jumped across summary swap: before={scroll_before}, after={scroll_after}"
    )


@pytest.mark.e2e
def test_harvest_arrow_key_row_nav(page: Page, live_server_harvest: str) -> None:
    """ArrowDown moves focus to the next ``tr`` in the harvest queue tbody.

    table_nav.js auto-assigns ``tabindex='0'`` to each <tr> under a
    ``tbody[data-table-nav]`` and intercepts ArrowDown/ArrowUp on keydown.
    """
    # The user-facing entry to the harvest plan is /positions?view=at-loss,
    # which loads /tax/harvest/plan as an HTMX fragment into #harvest-queue-region.
    # Only the full page boots Alpine, htmx, and table_nav.js — the bare fragment
    # has no <script> tags, so navigating to it directly would leave keyboard
    # nav disabled and palette JS uninitialized.
    page.goto(f"{live_server_harvest}/positions?view=at-loss", wait_until="networkidle", timeout=15_000)
    _suppress_overlays(page)
    page.wait_for_selector("tbody[data-table-nav] tr", timeout=5_000)

    row_count = page.locator("tbody[data-table-nav] tr").count()
    assert row_count >= 3, f"need at least 3 harvest rows to verify two ArrowDown steps; got {row_count}"

    # Focus the first row and press ArrowDown twice. After two presses, focus
    # should sit on row index 2 (zero-based).
    first_row = page.locator("tbody[data-table-nav] tr").first
    first_row.focus()
    page.keyboard.press("ArrowDown")
    page.keyboard.press("ArrowDown")

    focused_idx = page.evaluate(
        """
        () => {
            const rows = Array.from(document.querySelectorAll("tbody[data-table-nav] tr"));
            return rows.indexOf(document.activeElement);
        }
        """
    )
    assert focused_idx == 2, f"expected focus on row index 2 after two ArrowDowns, got {focused_idx}"
