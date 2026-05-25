"""Build the onboarding demo SQLite from in-code trade rows.

Renders DEMO_TAXABLE/DEMO_IRA to Schwab CSV format in memory, feeds through the
same parse-and-commit path real imports use (``SchwabParser`` +
``Repository.add_import``), then runs the wash-sale engine via
``stitch_account`` + ``recompute_all_violations``.
"""

from __future__ import annotations

import csv
import hashlib
import io
from datetime import datetime
from pathlib import Path

from net_alpha.brokers.registry import detect_broker
from net_alpha.brokers.schwab import SchwabParser
from net_alpha.db.connection import get_engine, init_db
from net_alpha.db.repository import Repository
from net_alpha.engine.etf_pairs import load_etf_pairs
from net_alpha.engine.recompute import recompute_all_violations
from net_alpha.engine.stitch import stitch_account
from net_alpha.ingest.dedup import filter_new
from net_alpha.models.domain import Account, ImportRecord
from net_alpha.web.demo.data import DEMO_IRA, DEMO_TAXABLE

_SCHWAB_HEADERS = ["Date", "Action", "Symbol", "Description", "Quantity", "Price", "Fees & Comm", "Amount"]


def _to_schwab_date(iso_date: str) -> str:
    return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%m/%d/%Y")


def _rows_to_schwab_csv(rows: list[dict[str, str]]) -> str:
    out = io.StringIO()
    out.write('"Transactions for account ...XXXX as of 2026-05-07"\n')
    writer = csv.DictWriter(out, fieldnames=_SCHWAB_HEADERS, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        rendered = {h: row.get(h, "") for h in _SCHWAB_HEADERS}
        date_value = row.get("Date", "")
        if date_value:
            rendered["Date"] = _to_schwab_date(date_value)
        writer.writerow(rendered)
    return out.getvalue()


def _parse_csv_text(csv_text: str) -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.reader(io.StringIO(csv_text))
    all_rows = [row for row in reader]
    if not all_rows:
        return [], []
    header_idx = 0
    for i, row in enumerate(all_rows[:5]):
        non_empty = [c.strip() for c in row if c.strip()]
        if len(non_empty) >= 4 and not any(c.startswith("$") for c in non_empty):
            header_idx = i
            break
    headers = [c.strip() for c in all_rows[header_idx]]
    data_rows: list[dict[str, str]] = []
    for raw in all_rows[header_idx + 1 :]:
        if not any(c.strip() for c in raw):
            continue
        padded = list(raw) + [""] * max(0, len(headers) - len(raw))
        data_rows.append({h: padded[i] for i, h in enumerate(headers)})
    return headers, data_rows


def _import_demo_account(
    repo: Repository,
    account_label: str,
    rows: list[dict[str, str]],
) -> list:
    csv_text = _rows_to_schwab_csv(rows)
    headers, parsed_rows = _parse_csv_text(csv_text)
    parser = detect_broker(headers)
    if not isinstance(parser, SchwabParser):
        raise RuntimeError(f"demo CSV not detected as Schwab (got {parser!r})")

    account: Account = repo.get_or_create_account("schwab", account_label)
    import_result = parser.parse_full(parsed_rows, account_display=account.display())
    trades = import_result.trades

    existing = repo.existing_natural_keys(account.id)
    new_trades = filter_new(trades, existing)

    record = ImportRecord(
        account_id=account.id,
        csv_filename=f"demo_{account_label}.csv",
        csv_sha256=hashlib.sha256(csv_text.encode("utf-8")).hexdigest(),
        imported_at=datetime.now(),
        trade_count=len(new_trades),
    )
    repo.add_import(account, record, new_trades, cash_events=import_result.cash_events)
    return [t.date for t in new_trades]


def build_demo_db(target: Path) -> None:
    target = Path(target)
    if target.exists():
        target.unlink()
    target.parent.mkdir(parents=True, exist_ok=True)

    engine = get_engine(target)
    init_db(engine)
    repo = Repository(engine)

    affected_dates: list = []
    affected_dates.extend(_import_demo_account(repo, "taxable", DEMO_TAXABLE))
    affected_dates.extend(_import_demo_account(repo, "ira", DEMO_IRA))

    # Type the demo "ira" account as a real IRA *before* the global recompute
    # below, so the cross-account NVDA loss (taxable sale → IRA rebuy) is
    # classified as a Rev. Rul. 2008-5 permanent wash sale — §1091(a) disallows
    # the loss but §1091(d) basis rollover and §1223(4) tacking are suppressed.
    # Without this the flagship IRA-trap feature is never exercised in the tour
    # and the IRA replacement lot wrongly shows a rolled-up basis.
    repo.set_account_type(broker="schwab", label="ira", type_="trad_ira")

    for account in repo.list_accounts():
        stitch_account(repo, account.id)

    if affected_dates:
        etf_pairs = load_etf_pairs(user_path=None)
        recompute_all_violations(repo, etf_pairs)
