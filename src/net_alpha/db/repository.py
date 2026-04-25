# src/net_alpha/db/repository.py
# NOTE: This is a v1→v2 transition stub. The v1 schema has been replaced by
# the v2 schema (AccountRow, ImportRecordRow, int PKs, natural_key, etc.).
# All repository classes that depended on v1 TradeRow/LotRow/WashSaleViolationRow
# are stubbed here and will be fully rewritten in Task 5.
# MetaRepository is the only class that remains functional.
from __future__ import annotations

from sqlmodel import Session, select

from net_alpha.db.tables import MetaRow


class TradeRepository:
    """Stub — full rewrite in Task 5."""

    def __init__(self, session: Session):
        self._session = session

    def save(self, trade) -> None:
        raise NotImplementedError("TradeRepository will be rewritten in Task 5 (v2 schema)")

    def save_batch(self, trades) -> None:
        raise NotImplementedError("TradeRepository will be rewritten in Task 5 (v2 schema)")

    def get_by_id(self, trade_id) -> None:
        raise NotImplementedError("TradeRepository will be rewritten in Task 5 (v2 schema)")

    def list_all(self) -> list:
        raise NotImplementedError("TradeRepository will be rewritten in Task 5 (v2 schema)")

    def list_by_account(self, account: str) -> list:
        raise NotImplementedError("TradeRepository will be rewritten in Task 5 (v2 schema)")

    def find_by_hash(self, raw_row_hash: str) -> None:
        raise NotImplementedError("TradeRepository will be rewritten in Task 5 (v2 schema)")

    def find_by_semantic_key(self, account, date_str, ticker, action, quantity, proceeds) -> None:
        raise NotImplementedError("TradeRepository will be rewritten in Task 5 (v2 schema)")

    def list_accounts(self) -> list:
        raise NotImplementedError("TradeRepository will be rewritten in Task 5 (v2 schema)")

    def count_by_account(self, account: str) -> int:
        raise NotImplementedError("TradeRepository will be rewritten in Task 5 (v2 schema)")

    def latest_trade_date_by_account(self, account: str) -> str | None:
        raise NotImplementedError("TradeRepository will be rewritten in Task 5 (v2 schema)")


class LotRepository:
    """Stub — full rewrite in Task 5."""

    def __init__(self, session: Session):
        self._session = session

    def save(self, lot) -> None:
        raise NotImplementedError("LotRepository will be rewritten in Task 5 (v2 schema)")

    def save_batch(self, lots) -> None:
        raise NotImplementedError("LotRepository will be rewritten in Task 5 (v2 schema)")

    def list_all(self) -> list:
        raise NotImplementedError("LotRepository will be rewritten in Task 5 (v2 schema)")

    def delete_all(self) -> None:
        raise NotImplementedError("LotRepository will be rewritten in Task 5 (v2 schema)")


class ViolationRepository:
    """Stub — full rewrite in Task 5."""

    def __init__(self, session: Session):
        self._session = session

    def save(self, violation) -> None:
        raise NotImplementedError("ViolationRepository will be rewritten in Task 5 (v2 schema)")

    def save_batch(self, violations) -> None:
        raise NotImplementedError("ViolationRepository will be rewritten in Task 5 (v2 schema)")

    def list_all(self) -> list:
        raise NotImplementedError("ViolationRepository will be rewritten in Task 5 (v2 schema)")

    def delete_all(self) -> None:
        raise NotImplementedError("ViolationRepository will be rewritten in Task 5 (v2 schema)")


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
