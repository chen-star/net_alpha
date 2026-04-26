# src/net_alpha/db/repository.py
from __future__ import annotations

from datetime import date

from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from net_alpha.db.tables import (
    AccountRow,
    ImportRecordRow,
    LotRow,
    MetaRow,
    TradeRow,
    WashSaleViolationRow,
)
from net_alpha.models.domain import (
    Account,
    AddImportResult,
    ImportRecord,
    ImportSummary,
    Lot,
    OptionDetails,
    RemoveImportResult,
    Trade,
    WashSaleViolation,
)


class Repository:
    """v2 repository — narrowed; one method per CLI need."""

    def __init__(self, engine: Engine):
        self.engine = engine

    # --- Account / import management ---

    def get_or_create_account(self, broker: str, label: str) -> Account:
        with Session(self.engine) as s:
            row = s.exec(select(AccountRow).where(AccountRow.broker == broker, AccountRow.label == label)).first()
            if row is None:
                row = AccountRow(broker=broker, label=label)
                s.add(row)
                s.commit()
                s.refresh(row)
            return Account(id=row.id, broker=row.broker, label=row.label)

    def get_account(self, broker: str, label: str) -> Account | None:
        with Session(self.engine) as s:
            row = s.exec(select(AccountRow).where(AccountRow.broker == broker, AccountRow.label == label)).first()
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
            rows = s.exec(select(TradeRow.natural_key).where(TradeRow.account_id == account_id)).all()
            return set(rows)

    def add_import(self, account: Account, record: ImportRecord, trades: list[Trade]) -> AddImportResult:
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

    # --- Reads ---

    def _row_to_trade(self, row: TradeRow, account_display: str) -> Trade:
        opt = None
        if row.option_strike is not None:
            opt = OptionDetails(
                strike=row.option_strike,
                expiry=date.fromisoformat(row.option_expiry),
                call_put=row.option_call_put,
            )
        return Trade(
            id=str(row.id),
            account=account_display,
            date=date.fromisoformat(row.trade_date),
            ticker=row.ticker,
            action=row.action,
            quantity=row.quantity,
            proceeds=row.proceeds,
            cost_basis=row.cost_basis,
            basis_unknown=row.basis_unknown,
            option_details=opt,
        )

    def _account_display_for_id(self, s: Session, account_id: int) -> str:
        a = s.get(AccountRow, account_id)
        return f"{a.broker}/{a.label}"

    def all_trades(self) -> list[Trade]:
        with Session(self.engine) as s:
            rows = s.exec(select(TradeRow)).all()
            return [self._row_to_trade(r, self._account_display_for_id(s, r.account_id)) for r in rows]

    def trades_in_window(self, start: date, end: date) -> list[Trade]:
        with Session(self.engine) as s:
            rows = s.exec(
                select(TradeRow).where(
                    TradeRow.trade_date >= start.isoformat(),
                    TradeRow.trade_date <= end.isoformat(),
                )
            ).all()
            return [self._row_to_trade(r, self._account_display_for_id(s, r.account_id)) for r in rows]

    def trades_for_import(self, import_id: int) -> list[Trade]:
        with Session(self.engine) as s:
            rows = s.exec(select(TradeRow).where(TradeRow.import_id == import_id)).all()
            return [self._row_to_trade(r, self._account_display_for_id(s, r.account_id)) for r in rows]

    def _row_to_lot(self, row: LotRow, account_display: str) -> Lot:
        opt = None
        if row.option_strike is not None:
            opt = OptionDetails(
                strike=row.option_strike,
                expiry=date.fromisoformat(row.option_expiry),
                call_put=row.option_call_put,
            )
        return Lot(
            id=str(row.id),
            trade_id=str(row.trade_id),
            account=account_display,
            date=date.fromisoformat(row.trade_date),
            ticker=row.ticker,
            quantity=row.quantity,
            cost_basis=row.cost_basis,
            adjusted_basis=row.adjusted_basis,
            option_details=opt,
        )

    def all_lots(self) -> list[Lot]:
        with Session(self.engine) as s:
            rows = s.exec(select(LotRow)).all()
            return [self._row_to_lot(r, self._account_display_for_id(s, r.account_id)) for r in rows]

    def _row_to_violation(self, s: Session, row: WashSaleViolationRow) -> WashSaleViolation:
        return WashSaleViolation(
            id=str(row.id),
            loss_trade_id=str(row.loss_trade_id),
            replacement_trade_id=str(row.replacement_trade_id),
            confidence=row.confidence,
            disallowed_loss=row.disallowed_loss,
            matched_quantity=row.matched_quantity,
            ticker=row.ticker,
            loss_account=self._account_display_for_id(s, row.loss_account_id),
            buy_account=self._account_display_for_id(s, row.buy_account_id),
            loss_sale_date=date.fromisoformat(row.loss_sale_date),
            triggering_buy_date=date.fromisoformat(row.triggering_buy_date),
        )

    def all_violations(self) -> list[WashSaleViolation]:
        with Session(self.engine) as s:
            rows = s.exec(select(WashSaleViolationRow)).all()
            return [self._row_to_violation(s, r) for r in rows]

    def violations_for_year(self, year: int) -> list[WashSaleViolation]:
        prefix = f"{year}-"
        with Session(self.engine) as s:
            rows = s.exec(
                select(WashSaleViolationRow).where(WashSaleViolationRow.loss_sale_date.startswith(prefix))
            ).all()
            return [self._row_to_violation(s, r) for r in rows]

    def list_distinct_tickers(self) -> list[str]:
        """All distinct tickers across all imported trades, sorted ascending."""
        with Session(self.engine) as s:
            rows = s.exec(select(TradeRow.ticker).distinct().order_by(TradeRow.ticker)).all()
            return list(rows)

    def get_trades_for_ticker(self, ticker: str) -> list[Trade]:
        """All trades for a ticker, sorted by trade_date ascending."""
        with Session(self.engine) as s:
            rows = s.exec(
                select(TradeRow).where(TradeRow.ticker == ticker).order_by(TradeRow.trade_date)
            ).all()
            return [self._row_to_trade(r, self._account_display_for_id(s, r.account_id)) for r in rows]

    def get_lots_for_ticker(self, ticker: str) -> list[Lot]:
        """Open lots for a ticker, sorted by trade_date ascending."""
        with Session(self.engine) as s:
            rows = s.exec(
                select(LotRow).where(LotRow.ticker == ticker).order_by(LotRow.trade_date)
            ).all()
            return [self._row_to_lot(r, self._account_display_for_id(s, r.account_id)) for r in rows]

    def get_violations_for_ticker(self, ticker: str) -> list[WashSaleViolation]:
        """All violations for a ticker, sorted by loss_sale_date ascending."""
        with Session(self.engine) as s:
            rows = s.exec(
                select(WashSaleViolationRow)
                .where(WashSaleViolationRow.ticker == ticker)
                .order_by(WashSaleViolationRow.loss_sale_date)
            ).all()
            return [self._row_to_violation(s, r) for r in rows]

    # --- Mutations ---

    def remove_import(self, import_id: int) -> RemoveImportResult:
        from datetime import timedelta

        with Session(self.engine) as s:
            trade_rows = s.exec(select(TradeRow).where(TradeRow.import_id == import_id)).all()
            trade_ids = [r.id for r in trade_rows]
            removed_dates = [date.fromisoformat(r.trade_date) for r in trade_rows]

            # Cascade-delete derived rows that reference these trades
            if trade_ids:
                s.exec(LotRow.__table__.delete().where(LotRow.trade_id.in_(trade_ids)))
                s.exec(
                    WashSaleViolationRow.__table__.delete().where(
                        (WashSaleViolationRow.loss_trade_id.in_(trade_ids))
                        | (WashSaleViolationRow.replacement_trade_id.in_(trade_ids))
                    )
                )
            s.exec(TradeRow.__table__.delete().where(TradeRow.import_id == import_id))
            s.exec(ImportRecordRow.__table__.delete().where(ImportRecordRow.id == import_id))
            s.commit()

            if not removed_dates:
                return RemoveImportResult(removed_trade_count=0, recompute_window=None)

            window = (
                min(removed_dates) - timedelta(days=30),
                max(removed_dates) + timedelta(days=30),
            )
            return RemoveImportResult(removed_trade_count=len(trade_ids), recompute_window=window)

    def replace_violations_in_window(self, start: date, end: date, new_violations: list[WashSaleViolation]) -> None:
        with Session(self.engine) as s:
            s.exec(
                WashSaleViolationRow.__table__.delete().where(
                    WashSaleViolationRow.loss_sale_date >= start.isoformat(),
                    WashSaleViolationRow.loss_sale_date <= end.isoformat(),
                )
            )
            for v in new_violations:
                s.add(self._violation_to_row(s, v))
            s.commit()

    def _violation_to_row(self, s: Session, v: WashSaleViolation) -> WashSaleViolationRow:
        # account_id resolution by display string ("schwab/personal")
        la = self._account_id_for_display(s, v.loss_account)
        ba = self._account_id_for_display(s, v.buy_account)
        return WashSaleViolationRow(
            loss_trade_id=int(v.loss_trade_id),
            replacement_trade_id=int(v.replacement_trade_id),
            loss_account_id=la,
            buy_account_id=ba,
            loss_sale_date=v.loss_sale_date.isoformat(),
            triggering_buy_date=v.triggering_buy_date.isoformat(),
            ticker=v.ticker,
            confidence=v.confidence,
            disallowed_loss=v.disallowed_loss,
            matched_quantity=v.matched_quantity,
        )

    def replace_lots_in_window(self, start: date, end: date, new_lots: list[Lot]) -> None:
        with Session(self.engine) as s:
            s.exec(
                LotRow.__table__.delete().where(
                    LotRow.trade_date >= start.isoformat(),
                    LotRow.trade_date <= end.isoformat(),
                )
            )
            for lot in new_lots:
                s.add(self._lot_to_row(s, lot))
            s.commit()

    def _lot_to_row(self, s: Session, lot: Lot) -> LotRow:
        # account is "schwab/personal"; trade_id is stringified int from _row_to_trade
        return LotRow(
            trade_id=int(lot.trade_id),
            account_id=self._account_id_for_display(s, lot.account),
            ticker=lot.ticker,
            trade_date=lot.date.isoformat(),
            quantity=lot.quantity,
            cost_basis=lot.cost_basis,
            adjusted_basis=lot.adjusted_basis,
            option_strike=(lot.option_details.strike if lot.option_details else None),
            option_expiry=(lot.option_details.expiry.isoformat() if lot.option_details else None),
            option_call_put=(lot.option_details.call_put if lot.option_details else None),
        )

    def _account_id_for_display(self, s: Session, display: str) -> int:
        broker, label = display.split("/", 1)
        row = s.exec(select(AccountRow).where(AccountRow.broker == broker, AccountRow.label == label)).first()
        if row is None:
            raise RuntimeError(f"no account row for {display!r}")
        return row.id


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
