# src/net_alpha/db/repository.py
from __future__ import annotations

from datetime import date

from sqlalchemy import distinct
from sqlmodel import Session, select

from net_alpha.db.tables import (
    LotRow,
    MetaRow,
    SchemaCacheRow,
    TradeRow,
    WashSaleViolationRow,
)
from net_alpha.models.domain import (
    Lot,
    OptionDetails,
    Trade,
    WashSaleViolation,
)


class TradeRepository:
    def __init__(self, session: Session):
        self._session = session

    def save(self, trade: Trade) -> None:
        row = _trade_to_row(trade)
        self._session.add(row)

    def save_batch(self, trades: list[Trade]) -> None:
        for trade in trades:
            self.save(trade)

    def get_by_id(self, trade_id: str) -> Trade | None:
        row = self._session.get(TradeRow, trade_id)
        if row is None:
            return None
        return _row_to_trade(row)

    def list_all(self) -> list[Trade]:
        rows = self._session.exec(select(TradeRow)).all()
        return [_row_to_trade(r) for r in rows]

    def list_by_account(self, account: str) -> list[Trade]:
        rows = self._session.exec(select(TradeRow).where(TradeRow.account == account)).all()
        return [_row_to_trade(r) for r in rows]

    def find_by_hash(self, raw_row_hash: str) -> Trade | None:
        row = self._session.exec(select(TradeRow).where(TradeRow.raw_row_hash == raw_row_hash)).first()
        if row is None:
            return None
        return _row_to_trade(row)

    def find_by_semantic_key(
        self,
        account: str,
        date_str: str,
        ticker: str,
        action: str,
        quantity: float,
        proceeds: float | None,
    ) -> Trade | None:
        stmt = select(TradeRow).where(
            TradeRow.account == account,
            TradeRow.date == date_str,
            TradeRow.ticker == ticker,
            TradeRow.action == action,
            TradeRow.quantity == quantity,
        )
        if proceeds is not None:
            stmt = stmt.where(TradeRow.proceeds == proceeds)
        else:
            stmt = stmt.where(TradeRow.proceeds.is_(None))
        row = self._session.exec(stmt).first()
        if row is None:
            return None
        return _row_to_trade(row)

    def list_accounts(self) -> list[str]:
        rows = self._session.exec(select(distinct(TradeRow.account))).all()
        return list(rows)

    def count_by_account(self, account: str) -> int:
        rows = self._session.exec(select(TradeRow).where(TradeRow.account == account)).all()
        return len(rows)

    def latest_trade_date_by_account(self, account: str) -> str | None:
        row = self._session.exec(
            select(TradeRow.date).where(TradeRow.account == account).order_by(TradeRow.date.desc())
        ).first()
        return row


class LotRepository:
    def __init__(self, session: Session):
        self._session = session

    def save(self, lot: Lot) -> None:
        row = _lot_to_row(lot)
        self._session.add(row)

    def save_batch(self, lots: list[Lot]) -> None:
        for lot in lots:
            self.save(lot)

    def list_all(self) -> list[Lot]:
        rows = self._session.exec(select(LotRow)).all()
        return [_row_to_lot(r) for r in rows]

    def delete_all(self) -> None:
        rows = self._session.exec(select(LotRow)).all()
        for row in rows:
            self._session.delete(row)


class ViolationRepository:
    def __init__(self, session: Session):
        self._session = session

    def save(self, violation: WashSaleViolation) -> None:
        row = _violation_to_row(violation)
        self._session.add(row)

    def save_batch(self, violations: list[WashSaleViolation]) -> None:
        for v in violations:
            self.save(v)

    def list_all(self) -> list[WashSaleViolation]:
        rows = self._session.exec(select(WashSaleViolationRow)).all()
        return [_row_to_violation(r) for r in rows]

    def delete_all(self) -> None:
        rows = self._session.exec(select(WashSaleViolationRow)).all()
        for row in rows:
            self._session.delete(row)


class MetaRepository:
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
    def __init__(self, session: Session):
        self._session = session

    def save(self, row: SchemaCacheRow) -> None:
        self._session.add(row)

    def find_by_broker_and_hash(self, broker_name: str, header_hash: str) -> SchemaCacheRow | None:
        return self._session.exec(
            select(SchemaCacheRow).where(
                SchemaCacheRow.broker_name == broker_name,
                SchemaCacheRow.header_hash == header_hash,
            )
        ).first()

    def list_by_broker(self, broker_name: str) -> list[SchemaCacheRow]:
        rows = self._session.exec(select(SchemaCacheRow).where(SchemaCacheRow.broker_name == broker_name)).all()
        return list(rows)


# --- Mapping functions: domain <-> table ---


def _trade_to_row(trade: Trade) -> TradeRow:
    row = TradeRow(
        id=trade.id,
        account=trade.account,
        date=trade.date.isoformat(),
        ticker=trade.ticker,
        action=trade.action,
        quantity=trade.quantity,
        proceeds=trade.proceeds,
        cost_basis=trade.cost_basis,
        basis_unknown=trade.basis_unknown,
        raw_row_hash=trade.raw_row_hash,
        schema_cache_id=trade.schema_cache_id,
    )
    if trade.option_details:
        row.option_strike = trade.option_details.strike
        row.option_expiry = trade.option_details.expiry.isoformat()
        row.option_call_put = trade.option_details.call_put
    return row


def _row_to_trade(row: TradeRow) -> Trade:
    option_details = None
    if row.option_strike is not None and row.option_call_put is not None:
        option_details = OptionDetails(
            strike=row.option_strike,
            expiry=date.fromisoformat(row.option_expiry),
            call_put=row.option_call_put,
        )
    return Trade(
        id=row.id,
        account=row.account,
        date=date.fromisoformat(row.date),
        ticker=row.ticker,
        action=row.action,
        quantity=row.quantity,
        proceeds=row.proceeds,
        cost_basis=row.cost_basis,
        basis_unknown=row.basis_unknown,
        option_details=option_details,
        raw_row_hash=row.raw_row_hash,
        schema_cache_id=row.schema_cache_id,
    )


def _lot_to_row(lot: Lot) -> LotRow:
    row = LotRow(
        id=lot.id,
        trade_id=lot.trade_id,
        account=lot.account,
        date=lot.date.isoformat(),
        ticker=lot.ticker,
        quantity=lot.quantity,
        cost_basis=lot.cost_basis,
        adjusted_basis=lot.adjusted_basis,
    )
    if lot.option_details:
        row.option_strike = lot.option_details.strike
        row.option_expiry = lot.option_details.expiry.isoformat()
        row.option_call_put = lot.option_details.call_put
    return row


def _row_to_lot(row: LotRow) -> Lot:
    option_details = None
    if row.option_strike is not None and row.option_call_put is not None:
        option_details = OptionDetails(
            strike=row.option_strike,
            expiry=date.fromisoformat(row.option_expiry),
            call_put=row.option_call_put,
        )
    return Lot(
        id=row.id,
        trade_id=row.trade_id,
        account=row.account,
        date=date.fromisoformat(row.date),
        ticker=row.ticker,
        quantity=row.quantity,
        cost_basis=row.cost_basis,
        adjusted_basis=row.adjusted_basis,
        option_details=option_details,
    )


def _violation_to_row(v: WashSaleViolation) -> WashSaleViolationRow:
    return WashSaleViolationRow(
        id=v.id,
        loss_trade_id=v.loss_trade_id,
        replacement_trade_id=v.replacement_trade_id,
        confidence=v.confidence,
        disallowed_loss=v.disallowed_loss,
        matched_quantity=v.matched_quantity,
    )


def _row_to_violation(row: WashSaleViolationRow) -> WashSaleViolation:
    return WashSaleViolation(
        id=row.id,
        loss_trade_id=row.loss_trade_id,
        replacement_trade_id=row.replacement_trade_id,
        confidence=row.confidence,
        disallowed_loss=row.disallowed_loss,
        matched_quantity=row.matched_quantity,
    )
