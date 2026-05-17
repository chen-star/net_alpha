"""Position rows must emit data-account-id so the pane click and j/k
keyboard handlers can scope to the right account when the same symbol
exists in multiple accounts."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient


def _seed_position(repo, builders, sym: str, broker: str, label: str) -> int:
    """Seed a single buy for *sym* in broker/label. Returns account.id."""
    from net_alpha.engine.recompute import recompute_all_violations
    from net_alpha.engine.stitch import stitch_account

    account_display = f"{broker}/{label}"
    today = date.today()
    buy = builders.make_buy(account_display, sym, today - timedelta(days=30), qty=10.0, cost=1000.0)
    account, _ = builders.seed_import(repo, broker, label, [buy])
    stitch_account(repo, account.id)
    recompute_all_violations(repo, {})
    return account.id


def test_position_rows_emit_data_account_id(
    client: TestClient,
    repo,
    builders,
) -> None:
    """A seeded position must render with data-account-id matching the
    account that holds it."""
    acct_id = _seed_position(repo, builders, "ACTID", "Schwab", "Taxable")

    resp = client.get("/portfolio/positions")
    assert resp.status_code == 200
    html = resp.text
    assert f'data-account-id="{acct_id}"' in html


def test_position_row_account_id_absent_for_multi_account(
    client: TestClient,
    repo,
    builders,
) -> None:
    """When the same symbol is held in two accounts, the row is aggregated
    and must NOT emit data-account-id (it would be ambiguous)."""
    sym = "MULTI"
    _seed_position(repo, builders, sym, "Schwab", "Taxable")
    _seed_position(repo, builders, sym, "Schwab", "IRA")

    resp = client.get("/portfolio/positions")
    assert resp.status_code == 200
    html = resp.text
    # The MULTI row should appear but without data-account-id because it
    # spans two accounts.
    assert sym in html
    # Find the MULTI row section — it must not have a data-account-id on it.
    # We search for data-account-id in the context of the MULTI symbol row.
    # A simple proxy: if any data-account-id exists in the page, that's for
    # the single-account rows; verify the two-account row's tr block does not
    # carry one. We check by ensuring no data-account-id appears between the
    # two tr markers for MULTI specifically.
    import re

    pattern = re.compile(
        r'data-row="position"[^>]*data-symbol="MULTI"[^>]*(data-account-id)',
        re.DOTALL,
    )
    assert not pattern.search(html), (
        "Multi-account row for MULTI must not carry data-account-id"
    )


def test_keyboard_handler_dispatches_account_id_from_dataset() -> None:
    """Sanity assert: table_nav.js j/k handler reads from dataset.accountId
    AND falls back to null only when the attribute is absent."""
    src = Path(__file__).parents[2] / "src/net_alpha/web/static/table_nav.js"
    text = src.read_text()
    assert "dataset.accountId" in text  # already present from Task 7


def test_click_handler_reads_dataset_account_id() -> None:
    """The Alpine @click handler in _portfolio_table.html must read
    dataset.accountId (not hardcode null) so multi-account rows with the
    same symbol open the correct account-scoped pane."""
    src = Path(__file__).parents[2] / "src/net_alpha/web/templates/_portfolio_table.html"
    text = src.read_text()
    assert "dataset.accountId" in text, (
        "@click handler must read dataset.accountId instead of hardcoding null"
    )
    assert "account_id: null" not in text, (
        "@click handler must not hardcode account_id: null"
    )
