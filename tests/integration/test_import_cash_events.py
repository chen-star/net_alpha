"""End-to-end: import both Schwab CSV fixtures, verify cash events round-trip
correctly per account, and that imports rm cleans them up."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

import pytest

from net_alpha.brokers.schwab import SchwabParser
from net_alpha.models.domain import ImportRecord


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open() as f:
        return list(csv.DictReader(f))


def _import(repo, label: str, rows: list[dict[str, str]]) -> int:
    parser = SchwabParser()
    account = repo.get_or_create_account("Schwab", label)
    result = parser.parse_full(rows, f"Schwab/{label}")
    rec = ImportRecord(
        id=None,
        account_id=account.id,
        csv_filename=f"{label}.csv",
        csv_sha256="",
        imported_at=datetime(2026, 4, 26, 12, 0, 0),
        trade_count=0,
    )
    return repo.add_import(
        account, rec,
        trades=result.trades,
        cash_events=result.cash_events,
    ).import_id


def test_import_both_csvs_yields_per_account_cash_events(repo):  # uses existing repo fixture
    st_rows = _read_rows(FIXTURES / "schwab_short_term.csv")
    lt_rows = _read_rows(FIXTURES / "schwab_long_term.csv")
    _import(repo, "short_term", st_rows)
    _import(repo, "long_term", lt_rows)

    short_acct = repo.get_account("Schwab", "short_term")
    long_acct = repo.get_account("Schwab", "long_term")

    short = repo.list_cash_events(account_id=short_acct.id)
    long = repo.list_cash_events(account_id=long_acct.id)

    assert len(short) > 0
    assert len(long) > 0
    assert all(e.account == "Schwab/short_term" for e in short)
    assert all(e.account == "Schwab/long_term" for e in long)


def test_imports_cover_all_expected_cash_event_kinds(repo):
    _import(repo, "short_term", _read_rows(FIXTURES / "schwab_short_term.csv"))
    _import(repo, "long_term", _read_rows(FIXTURES / "schwab_long_term.csv"))

    kinds = {e.kind for e in repo.list_cash_events()}
    # ST has these (from inspection of the CSV):
    assert "transfer_in" in kinds  # MoneyLink Transfer
    assert "dividend" in kinds     # Cash Dividend / Qualified / Non-Qualified
    assert "interest" in kinds     # Credit Interest
    # ST also has Futures MM Sweep (both directions)
    assert "sweep_out" in kinds or "sweep_in" in kinds
    # LT has Foreign Tax Paid + ADR Mgmt Fee
    assert "fee" in kinds


def test_remove_import_cleans_only_that_imports_cash_events(repo):
    st_id = _import(repo, "short_term", _read_rows(FIXTURES / "schwab_short_term.csv"))
    _import(repo, "long_term", _read_rows(FIXTURES / "schwab_long_term.csv"))

    long_acct = repo.get_account("Schwab", "long_term")
    short_acct = repo.get_account("Schwab", "short_term")

    long_before = len(repo.list_cash_events(account_id=long_acct.id))
    repo.remove_import(st_id)

    short_after = len(repo.list_cash_events(account_id=short_acct.id))
    long_after = len(repo.list_cash_events(account_id=long_acct.id))

    assert short_after == 0  # all ST cash events gone
    assert long_after == long_before  # LT untouched


def test_reimport_same_csv_dedups_cash_events(repo):
    rows = _read_rows(FIXTURES / "schwab_short_term.csv")
    _import(repo, "short_term", rows)
    first_count = len(repo.list_cash_events())
    _import(repo, "short_term", rows)  # re-import same file
    second_count = len(repo.list_cash_events())

    assert first_count > 0
    assert second_count == first_count  # natural_key UNIQUE constraint dedup
