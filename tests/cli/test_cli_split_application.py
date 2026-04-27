"""Verify CLI flows that touch lots also apply splits + manual overrides
(parity with the web routes).

These tests exercise the CliRunner path — the same code the user hits — so
that remove_cmd / run_cmd route through recompute_all_violations (which calls
apply_splits + apply_manual_overrides) and not the bare
detect_in_window + replace_lots_in_window shortcut.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest
from typer.testing import CliRunner

from net_alpha.db.connection import init_db
from net_alpha.db.repository import Repository
from net_alpha.models.domain import Account, ImportRecord, Trade

# ---------------------------------------------------------------------------
# Helpers (mirror tests/splits/conftest.py pattern)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_cli_imports_rm_reapplies_unapplied_split_for_remaining_lots(tmp_path, monkeypatch):
    """When CLI 'imports rm' removes one import, the remaining lots for a
    *different* ticker that has a split registered (but not yet applied)
    must be split-adjusted by the recompute_all_violations triggered inside
    remove_cmd.

    Scenario:
      - Import TSLA (to be unimported) and SQQQ (stays).
      - Seed a SQQQ split AFTER the initial recompute (so no override exists yet).
      - Unimport TSLA via CLI → recompute_all_violations → apply_splits runs
        and finds no prior override for SQQQ → applies the split.
    """
    from sqlmodel import create_engine

    from net_alpha.cli.app import app
    from net_alpha.engine.etf_pairs import load_etf_pairs
    from net_alpha.engine.recompute import recompute_all_violations

    # Point HOME at tmp_path so _engine() uses our temp DB.
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".net_alpha").mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / ".net_alpha" / "net_alpha.db"

    eng = create_engine(f"sqlite:///{db_path}")
    init_db(eng)
    repo = Repository(eng)

    # First import: TSLA (will be unimported).
    _seed_import(
        repo,
        "schwab",
        "lt",
        [_make_buy("schwab/lt", "TSLA", date(2024, 1, 5), qty=10, cost=2000)],
        csv_filename="first.csv",
    )
    # Second import: SQQQ (stays).
    _seed_import(
        repo,
        "schwab",
        "lt",
        [_make_buy("schwab/lt", "SQQQ", date(2024, 6, 1), qty=100, cost=5000)],
        csv_filename="second.csv",
    )

    # Initial recompute — no splits yet, lots at raw quantities.
    etf_pairs = load_etf_pairs()
    recompute_all_violations(repo, etf_pairs)

    # Register a split for SQQQ AFTER the initial recompute (so no override exists).
    # ratio=0.1 → qty * 0.1.
    repo.add_split("SQQQ", date(2025, 1, 13), 0.1, "yahoo")

    # Sanity: SQQQ lot is still at raw quantity because the split wasn't applied yet.
    lots_before = repo.get_lots_for_ticker("SQQQ")
    assert len(lots_before) == 1
    assert lots_before[0].quantity == pytest.approx(100.0)

    # Identify TSLA import id to unimport.
    imports = repo.list_imports()
    tsla_import = next(i for i in imports if i.csv_filename == "first.csv")

    # Use the actual CLI path: `net-alpha imports rm <id> --yes`.
    cli_runner = CliRunner()
    result = cli_runner.invoke(app, ["imports", "rm", str(tsla_import.id), "--yes"])
    assert result.exit_code == 0, f"CLI imports rm failed:\n{result.stdout}"

    # recompute_all_violations inside remove_cmd called apply_splits.
    # SQQQ lot had no prior split override → split must now be applied: 100 * 0.1 = 10.0.
    lots_after = repo.get_lots_for_ticker("SQQQ")
    assert len(lots_after) == 1, f"Expected 1 SQQQ lot, got {len(lots_after)}"
    remaining_qty = lots_after[0].quantity
    assert remaining_qty == pytest.approx(10.0), (
        f"Lot quantity should be split-adjusted to 10.0, got {remaining_qty}. "
        "apply_splits was not called after the CLI unimport."
    )


def test_cli_default_run_applies_unapplied_split(tmp_path, monkeypatch):
    """When the CLI default run imports a new ticker, apply_splits is called
    during the recompute_all_violations triggered at the end of run().

    Scenario:
      - Pre-seed an AAPL import.
      - Register an AAPL split AFTER the initial recompute (no override yet).
      - Import TSLA via the CLI — triggers recompute_all_violations which
        calls apply_splits → AAPL lot gets split-adjusted for the first time.
    """
    from sqlmodel import create_engine

    from net_alpha.cli.app import app
    from net_alpha.engine.etf_pairs import load_etf_pairs
    from net_alpha.engine.recompute import recompute_all_violations

    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".net_alpha").mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / ".net_alpha" / "net_alpha.db"

    eng = create_engine(f"sqlite:///{db_path}")
    init_db(eng)
    repo = Repository(eng)

    # Pre-seed AAPL via repo (not CLI, to avoid network calls).
    _seed_import(
        repo,
        "schwab",
        "personal",
        [_make_buy("schwab/personal", "AAPL", date(2024, 1, 5), qty=200, cost=30000)],
        csv_filename="aapl_preseed.csv",
    )
    # Initial recompute — no splits yet.
    etf_pairs = load_etf_pairs()
    recompute_all_violations(repo, etf_pairs)

    lots = repo.get_lots_for_ticker("AAPL")
    assert lots[0].quantity == pytest.approx(200.0)

    # Register a 4:1 split for AAPL (ratio=4.0) AFTER the initial recompute.
    # No override exists yet for this trade_id + split_id pair.
    repo.add_split("AAPL", date(2024, 6, 10), 4.0, "manual_test")

    # Import TSLA via CLI — triggers recompute_all_violations → apply_splits.
    # TSLA is a new equity → _post_import_autosync_splits will attempt a Yahoo
    # fetch for it. We don't want that. Use a ticker that parses as a buy but
    # whose split fetch will not interfere with AAPL. Since network calls might
    # be slow/fail, use monkeypatch to short-circuit _post_import_autosync_splits.
    from unittest.mock import patch

    csv_path = tmp_path / "tsla.csv"
    csv_path.write_text("Date,Action,Symbol,Quantity,Price,Amount\n08/01/2024,Buy,TSLA,5,$200.00,$-1000.00\n")

    cli_runner = CliRunner()
    with patch("net_alpha.cli.default._post_import_autosync_splits"):
        result = cli_runner.invoke(app, [str(csv_path), "--account", "personal"])
    assert result.exit_code == 0, f"CLI default run failed:\n{result.stdout}"

    # AAPL lot must now be split-adjusted: 200 * 4.0 = 800.0.
    lots_after = repo.get_lots_for_ticker("AAPL")
    assert len(lots_after) == 1
    assert lots_after[0].quantity == pytest.approx(800.0), (
        f"Expected AAPL lot split-adjusted to 800.0, got {lots_after[0].quantity}. "
        "apply_splits was not called after CLI default import."
    )
