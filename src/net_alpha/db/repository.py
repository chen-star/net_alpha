# src/net_alpha/db/repository.py
from __future__ import annotations

from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from net_alpha.db.tables import (
    AccountRow,
    ImportRecordRow,
    MetaRow,
    TradeRow,
)
from net_alpha.models.domain import (
    Account,
    AddImportResult,
    ImportRecord,
    ImportSummary,
    Trade,
)


class Repository:
    """v2 repository — narrowed; one method per CLI need."""

    def __init__(self, engine: Engine):
        self.engine = engine

    # --- Account / import management ---

    def get_or_create_account(self, broker: str, label: str) -> Account:
        with Session(self.engine) as s:
            row = s.exec(
                select(AccountRow).where(AccountRow.broker == broker, AccountRow.label == label)
            ).first()
            if row is None:
                row = AccountRow(broker=broker, label=label)
                s.add(row)
                s.commit()
                s.refresh(row)
            return Account(id=row.id, broker=row.broker, label=row.label)

    def get_account(self, broker: str, label: str) -> Account | None:
        with Session(self.engine) as s:
            row = s.exec(
                select(AccountRow).where(AccountRow.broker == broker, AccountRow.label == label)
            ).first()
            if row is None:
                return None
            return Account(id=row.id, broker=row.broker, label=row.label)

    def list_accounts(self) -> list[Account]:
        with Session(self.engine) as s:
            rows = s.exec(select(AccountRow)).all()
            return [Account(id=r.id, broker=r.broker, label=r.label) for r in rows]

    def list_imports(self) -> list[ImportSummary]:
        with Session(self.engine) as s:
            stmt = (
                select(ImportRecordRow, AccountRow)
                .join(AccountRow, AccountRow.id == ImportRecordRow.account_id)
                .order_by(ImportRecordRow.imported_at.desc())
            )
            return [
                ImportSummary(
                    id=ir.id,
                    account_display=f"{a.broker}/{a.label}",
                    csv_filename=ir.csv_filename,
                    trade_count=ir.trade_count,
                    imported_at=ir.imported_at,
                )
                for ir, a in s.exec(stmt).all()
            ]

    def get_import(self, import_id: int) -> ImportRecord | None:
        with Session(self.engine) as s:
            row = s.get(ImportRecordRow, import_id)
            if row is None:
                return None
            return ImportRecord(
                id=row.id,
                account_id=row.account_id,
                csv_filename=row.csv_filename,
                csv_sha256=row.csv_sha256,
                imported_at=row.imported_at,
                trade_count=row.trade_count,
            )

    def existing_natural_keys(self, account_id: int) -> set[str]:
        with Session(self.engine) as s:
            rows = s.exec(
                select(TradeRow.natural_key).where(TradeRow.account_id == account_id)
            ).all()
            return set(rows)

    def add_import(
        self, account: Account, record: ImportRecord, trades: list[Trade]
    ) -> AddImportResult:
        """Insert trades for a new ImportRecord. Caller should pre-filter dups
        with existing_natural_keys; we still rely on the UNIQUE constraint as
        the safety net for anything the caller missed.
        """
        with Session(self.engine) as s:
            ir = ImportRecordRow(
                account_id=account.id,
                csv_filename=record.csv_filename,
                csv_sha256=record.csv_sha256,
                imported_at=record.imported_at,
                trade_count=len(trades),
            )
            s.add(ir)
            s.flush()  # populate ir.id

            new_count = 0
            dup_count = 0
            for t in trades:
                tr = TradeRow(
                    import_id=ir.id,
                    account_id=account.id,
                    natural_key=t.compute_natural_key(),
                    ticker=t.ticker,
                    trade_date=t.date.isoformat(),
                    action=t.action,
                    quantity=t.quantity,
                    proceeds=t.proceeds,
                    cost_basis=t.cost_basis,
                    basis_unknown=t.basis_unknown,
                    option_strike=(t.option_details.strike if t.option_details else None),
                    option_expiry=(t.option_details.expiry.isoformat() if t.option_details else None),
                    option_call_put=(t.option_details.call_put if t.option_details else None),
                )
                try:
                    s.add(tr)
                    s.flush()
                    new_count += 1
                except Exception:  # IntegrityError on UNIQUE
                    s.rollback()
                    # Reattach the ImportRecord row before retrying the next trade
                    s.add(ir)
                    dup_count += 1

            ir.trade_count = new_count
            s.commit()
            return AddImportResult(import_id=ir.id, new_trades=new_count, duplicate_trades=dup_count)

    # Methods added in later tasks: trades_for_import, remove_import,
    # all_trades, all_lots, all_violations,
    # violations_for_year, trades_in_window, replace_violations_in_window


# ---------------------------------------------------------------------------
# Legacy / preserved classes — kept for import compatibility
# ---------------------------------------------------------------------------


class MetaRepository:
    """Functional — MetaRow schema is unchanged in v2."""

    def __init__(self, session: Session):
        self._session = session

    def get(self, key: str) -> str | None:
        row = self._session.exec(select(MetaRow).where(MetaRow.key == key)).first()
        return row.value if row else None

    def set(self, key: str, value: str) -> None:
        row = self._session.exec(select(MetaRow).where(MetaRow.key == key)).first()
        if row:
            row.value = value
            self._session.add(row)
        else:
            self._session.add(MetaRow(key=key, value=value))


class TradeRepository:
    """Stub — kept for import compatibility; will be removed in a later task."""

    def __init__(self, session: Session):
        self._session = session

    def save(self, trade) -> None:
        raise NotImplementedError("TradeRepository will be rewritten in Task 6 (v2 schema)")

    def save_batch(self, trades) -> None:
        raise NotImplementedError("TradeRepository will be rewritten in Task 6 (v2 schema)")

    def get_by_id(self, trade_id) -> None:
        raise NotImplementedError("TradeRepository will be rewritten in Task 6 (v2 schema)")

    def list_all(self) -> list:
        raise NotImplementedError("TradeRepository will be rewritten in Task 6 (v2 schema)")

    def list_by_account(self, account: str) -> list:
        raise NotImplementedError("TradeRepository will be rewritten in Task 6 (v2 schema)")

    def find_by_hash(self, raw_row_hash: str) -> None:
        raise NotImplementedError("TradeRepository will be rewritten in Task 6 (v2 schema)")

    def find_by_semantic_key(self, account, date_str, ticker, action, quantity, proceeds) -> None:
        raise NotImplementedError("TradeRepository will be rewritten in Task 6 (v2 schema)")

    def list_accounts(self) -> list:
        raise NotImplementedError("TradeRepository will be rewritten in Task 6 (v2 schema)")

    def count_by_account(self, account: str) -> int:
        raise NotImplementedError("TradeRepository will be rewritten in Task 6 (v2 schema)")

    def latest_trade_date_by_account(self, account: str) -> str | None:
        raise NotImplementedError("TradeRepository will be rewritten in Task 6 (v2 schema)")


class LotRepository:
    """Stub — kept for import compatibility; will be removed in a later task."""

    def __init__(self, session: Session):
        self._session = session

    def save(self, lot) -> None:
        raise NotImplementedError("LotRepository will be rewritten in Task 6 (v2 schema)")

    def save_batch(self, lots) -> None:
        raise NotImplementedError("LotRepository will be rewritten in Task 6 (v2 schema)")

    def list_all(self) -> list:
        raise NotImplementedError("LotRepository will be rewritten in Task 6 (v2 schema)")

    def delete_all(self) -> None:
        raise NotImplementedError("LotRepository will be rewritten in Task 6 (v2 schema)")


class ViolationRepository:
    """Stub — kept for import compatibility; will be removed in a later task."""

    def __init__(self, session: Session):
        self._session = session

    def save(self, violation) -> None:
        raise NotImplementedError("ViolationRepository will be rewritten in Task 6 (v2 schema)")

    def save_batch(self, violations) -> None:
        raise NotImplementedError("ViolationRepository will be rewritten in Task 6 (v2 schema)")

    def list_all(self) -> list:
        raise NotImplementedError("ViolationRepository will be rewritten in Task 6 (v2 schema)")

    def delete_all(self) -> None:
        raise NotImplementedError("ViolationRepository will be rewritten in Task 6 (v2 schema)")


class SchemaCacheRepository:
    """Removed in v2 — schema cache is gone (no LLM in v2). Stub for import compat."""

    def __init__(self, session: Session):
        self._session = session

    def save(self, row) -> None:
        raise NotImplementedError("SchemaCacheRepository removed in v2 (no LLM schema cache)")

    def find_by_broker_and_hash(self, broker_name: str, header_hash: str) -> None:
        raise NotImplementedError("SchemaCacheRepository removed in v2 (no LLM schema cache)")

    def list_by_broker(self, broker_name: str) -> list:
        raise NotImplementedError("SchemaCacheRepository removed in v2 (no LLM schema cache)")
