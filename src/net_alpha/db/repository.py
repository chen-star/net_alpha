# src/net_alpha/db/repository.py
from __future__ import annotations

import json
from datetime import date
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from net_alpha.db.tables import (
    AccountRow,
    ImportRecordRow,
    LotRow,
    MetaRow,
    RealizedGLLotRow,
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
from net_alpha.models.realized_gl import RealizedGLLot


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
            out: list[ImportSummary] = []
            for ir, a in s.exec(stmt).all():
                gl_count = s.exec(
                    select(func.count(RealizedGLLotRow.id)).where(RealizedGLLotRow.import_id == ir.id)
                ).one()
                out.append(
                    ImportSummary(
                        id=ir.id,
                        account_display=f"{a.broker}/{a.label}",
                        csv_filename=ir.csv_filename,
                        trade_count=ir.trade_count,
                        imported_at=ir.imported_at,
                        gl_lot_count=int(gl_count or 0),
                        min_trade_date=date.fromisoformat(ir.min_trade_date) if ir.min_trade_date else None,
                        max_trade_date=date.fromisoformat(ir.max_trade_date) if ir.max_trade_date else None,
                        equity_count=ir.equity_count,
                        option_count=ir.option_count,
                        option_expiry_count=ir.option_expiry_count,
                        parse_warnings=json.loads(ir.parse_warnings_json) if ir.parse_warnings_json else [],
                        duplicate_trades=ir.duplicate_trades or 0,
                    )
                )
            return out

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
                min_trade_date=record.min_trade_date.isoformat() if record.min_trade_date else None,
                max_trade_date=record.max_trade_date.isoformat() if record.max_trade_date else None,
                equity_count=record.equity_count,
                option_count=record.option_count,
                option_expiry_count=record.option_expiry_count,
                parse_warnings_json=json.dumps(record.parse_warnings) if record.parse_warnings else None,
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
                    basis_source=t.basis_source,
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
            # `record.duplicate_trades` is the pre-filter count from the upload
            # route (caller dedup'd against existing_natural_keys). `dup_count`
            # is the runtime UNIQUE-constraint fallback. Sum so the displayed
            # number matches what the user actually skipped.
            ir.duplicate_trades = (record.duplicate_trades or 0) + dup_count
            s.commit()
            return AddImportResult(
                import_id=ir.id,
                new_trades=new_count,
                duplicate_trades=ir.duplicate_trades,
            )

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
            basis_source=row.basis_source,
            is_manual=row.is_manual,
            transfer_basis_user_set=row.transfer_basis_user_set,
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
            source=row.source,
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
            rows = s.exec(select(TradeRow).where(TradeRow.ticker == ticker).order_by(TradeRow.trade_date)).all()
            return [self._row_to_trade(r, self._account_display_for_id(s, r.account_id)) for r in rows]

    def get_lots_for_ticker(self, ticker: str) -> list[Lot]:
        """Open lots for a ticker, sorted by trade_date ascending."""
        with Session(self.engine) as s:
            rows = s.exec(select(LotRow).where(LotRow.ticker == ticker).order_by(LotRow.trade_date)).all()
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
            # Delete G/L lots tied to this import (added in schema v2)
            s.exec(RealizedGLLotRow.__table__.delete().where(RealizedGLLotRow.import_id == import_id))
            s.exec(ImportRecordRow.__table__.delete().where(ImportRecordRow.id == import_id))
            s.commit()

            if not removed_dates:
                return RemoveImportResult(removed_trade_count=0, recompute_window=None)

            window = (
                min(removed_dates) - timedelta(days=30),
                max(removed_dates) + timedelta(days=30),
            )
            return RemoveImportResult(removed_trade_count=len(trade_ids), recompute_window=window)

    def update_import_aggregates(
        self,
        *,
        import_id: int,
        min_trade_date: date | None,
        max_trade_date: date | None,
        equity_count: int,
        option_count: int,
        option_expiry_count: int,
        parse_warnings: list[str],
    ) -> None:
        """Persist aggregate columns. Used by the backfill helper."""
        with Session(self.engine) as s:
            row = s.get(ImportRecordRow, import_id)
            if row is None:
                raise LookupError(f"Import #{import_id} not found")
            row.min_trade_date = min_trade_date.isoformat() if min_trade_date else None
            row.max_trade_date = max_trade_date.isoformat() if max_trade_date else None
            row.equity_count = equity_count
            row.option_count = option_count
            row.option_expiry_count = option_expiry_count
            row.parse_warnings_json = json.dumps(parse_warnings) if parse_warnings else None
            s.add(row)
            s.commit()

    def get_import_detail(self, import_id: int) -> dict | None:
        """Return a dict of detail-panel fields for the imports detail fragment.

        Includes: aggregate columns, plus an account hint (the first ticker count),
        plus distinct-ticker info pulled live from the joined trade rows.
        Returns None if the import does not exist.
        """
        rec = self.get_import(import_id)
        if rec is None:
            return None
        trades = self.trades_for_import(import_id)
        distinct_tickers = sorted({t.ticker for t in trades})
        with Session(self.engine) as s:
            ir = s.get(ImportRecordRow, import_id)
            account_row = s.exec(select(AccountRow).where(AccountRow.id == ir.account_id)).first()
            broker = account_row.broker if account_row else "unknown"
            label = account_row.label if account_row else "unknown"
            warnings = []
            if ir.parse_warnings_json:
                warnings = json.loads(ir.parse_warnings_json)
            min_td = date.fromisoformat(ir.min_trade_date) if ir.min_trade_date else None
            max_td = date.fromisoformat(ir.max_trade_date) if ir.max_trade_date else None
            equity_count = ir.equity_count or 0
            option_count = ir.option_count or 0
            option_expiry_count = ir.option_expiry_count or 0
        return {
            "id": import_id,
            "broker": broker,
            "account_label": label,
            "csv_filename": rec.csv_filename,
            "min_trade_date": min_td,
            "max_trade_date": max_td,
            "equity_count": equity_count,
            "option_count": option_count,
            "option_expiry_count": option_expiry_count,
            "distinct_ticker_count": len(distinct_tickers),
            "tickers_preview": distinct_tickers[:5],
            "parse_warnings": warnings,
        }

    def replace_violations_in_window(self, start: date, end: date, new_violations: list[WashSaleViolation]) -> None:
        with Session(self.engine) as s:
            s.exec(
                WashSaleViolationRow.__table__.delete().where(
                    WashSaleViolationRow.loss_sale_date >= start.isoformat(),
                    WashSaleViolationRow.loss_sale_date <= end.isoformat(),
                )
            )
            for v in new_violations:
                try:
                    s.add(self._violation_to_row(s, v))
                except LookupError:
                    # Schwab G/L violation has no matching Sell trade in the DB
                    # (e.g. G/L imported without Transaction History) — skip silently.
                    pass
            s.commit()

    def _violation_to_row(self, s: Session, v: WashSaleViolation) -> WashSaleViolationRow:
        # account_id resolution by display string ("schwab/personal")
        la = self._account_id_for_display(s, v.loss_account)
        ba = self._account_id_for_display(s, v.buy_account)

        if getattr(v, "source", "engine") == "schwab_g_l":
            # Synthetic IDs like "schwab_gl_<hash>" can't be int()-cast.
            # Resolve to the real TradeRow by matching the Sell trade for this
            # account+ticker+date.  Raise LookupError when none found so the
            # caller can skip this violation cleanly.
            sell_row = s.exec(
                select(TradeRow).where(
                    TradeRow.account_id == la,
                    TradeRow.ticker == v.ticker,
                    TradeRow.action == "Sell",
                    TradeRow.trade_date == v.loss_sale_date.isoformat(),
                )
            ).first()
            if sell_row is None:
                raise LookupError(f"No Sell trade found for Schwab G/L violation on {v.ticker} {v.loss_sale_date}")
            trade_id = sell_row.id
            loss_trade_id = trade_id
            replacement_trade_id = trade_id
        else:
            loss_trade_id = int(v.loss_trade_id)
            replacement_trade_id = int(v.replacement_trade_id)

        return WashSaleViolationRow(
            loss_trade_id=loss_trade_id,
            replacement_trade_id=replacement_trade_id,
            loss_account_id=la,
            buy_account_id=ba,
            loss_sale_date=v.loss_sale_date.isoformat(),
            triggering_buy_date=v.triggering_buy_date.isoformat(),
            ticker=v.ticker,
            confidence=v.confidence,
            disallowed_loss=v.disallowed_loss,
            matched_quantity=v.matched_quantity,
            source=getattr(v, "source", "engine"),
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

    # ----- Realized G/L methods (schema v2) -----

    def add_gl_lots(self, account: Account, import_id: int, lots: list[RealizedGLLot]) -> int:
        """Insert G/L lots, deduplicated on natural_key. Returns count of new rows."""
        if account.id is None:
            raise ValueError("Account must have an id")
        inserted = 0
        with Session(self.engine) as s:
            existing = set(
                s.exec(select(RealizedGLLotRow.natural_key).where(RealizedGLLotRow.account_id == account.id)).all()
            )
            for lot in lots:
                key = lot.compute_natural_key()
                if key in existing:
                    continue
                row = RealizedGLLotRow(
                    import_id=import_id,
                    account_id=account.id,
                    symbol_raw=lot.symbol_raw,
                    ticker=lot.ticker,
                    closed_date=lot.closed_date.isoformat(),
                    opened_date=lot.opened_date.isoformat(),
                    quantity=lot.quantity,
                    proceeds=lot.proceeds,
                    cost_basis=lot.cost_basis,
                    unadjusted_cost_basis=lot.unadjusted_cost_basis,
                    wash_sale=lot.wash_sale,
                    disallowed_loss=lot.disallowed_loss,
                    term=lot.term,
                    option_strike=lot.option_strike,
                    option_expiry=lot.option_expiry,
                    option_call_put=lot.option_call_put,
                    natural_key=key,
                )
                s.add(row)
                existing.add(key)
                inserted += 1
            s.commit()
        return inserted

    def get_gl_lots_for_match(self, *, account_id: int, symbol_raw: str, closed_date: date) -> list[RealizedGLLot]:
        """All G/L lots in this account that match a Sell trade by symbol+closed_date."""
        with Session(self.engine) as s:
            rows = s.exec(
                select(RealizedGLLotRow).where(
                    RealizedGLLotRow.account_id == account_id,
                    RealizedGLLotRow.symbol_raw == symbol_raw,
                    RealizedGLLotRow.closed_date == closed_date.isoformat(),
                )
            ).all()
            account_display = self._account_display_for_id(s, account_id)
        return [self._row_to_gl_lot(r, account_display) for r in rows]

    def get_gl_lots_for_ticker(self, account_id: int, ticker: str) -> list[RealizedGLLot]:
        """All G/L lots for a ticker in this account, sorted by closed_date."""
        with Session(self.engine) as s:
            rows = s.exec(
                select(RealizedGLLotRow)
                .where(
                    RealizedGLLotRow.account_id == account_id,
                    RealizedGLLotRow.ticker == ticker,
                )
                .order_by(RealizedGLLotRow.closed_date)
            ).all()
            account_display = self._account_display_for_id(s, account_id)
        return [self._row_to_gl_lot(r, account_display) for r in rows]

    def get_equity_gl_closures(self) -> dict[tuple[str, str], float]:
        """Sum of closed equity quantity per (account_display, ticker) across all GL lots.

        Used by position aggregations to compute true open quantity when the user
        has imported a Realized G/L CSV without the matching Transaction History
        (so trade-table sells are incomplete). Options are excluded — only rows
        with no option_strike contribute.
        """
        out: dict[tuple[str, str], float] = {}
        with Session(self.engine) as s:
            rows = s.exec(select(RealizedGLLotRow).where(RealizedGLLotRow.option_strike.is_(None))).all()
            for r in rows:
                display = self._account_display_for_id(s, r.account_id)
                key = (display, r.ticker)
                out[key] = out.get(key, 0.0) + float(r.quantity)
        return out

    def get_gl_lots_for_account(self, account_id: int) -> list[RealizedGLLot]:
        with Session(self.engine) as s:
            rows = s.exec(select(RealizedGLLotRow).where(RealizedGLLotRow.account_id == account_id)).all()
            account_display = self._account_display_for_id(s, account_id)
        return [self._row_to_gl_lot(r, account_display) for r in rows]

    def _row_to_gl_lot(self, row: RealizedGLLotRow, account_display: str) -> RealizedGLLot:
        return RealizedGLLot(
            account_display=account_display,
            symbol_raw=row.symbol_raw,
            ticker=row.ticker,
            closed_date=date.fromisoformat(row.closed_date),
            opened_date=date.fromisoformat(row.opened_date),
            quantity=row.quantity,
            proceeds=row.proceeds,
            cost_basis=row.cost_basis,
            unadjusted_cost_basis=row.unadjusted_cost_basis,
            wash_sale=row.wash_sale,
            disallowed_loss=row.disallowed_loss,
            term=row.term,
            option_strike=row.option_strike,
            option_expiry=row.option_expiry,
            option_call_put=row.option_call_put,
        )

    # ----- Stitch helpers (schema v2) -----

    def get_sells_for_account(self, account_id: int) -> list[Trade]:
        """All Sell trades in this account. Used by stitch as input set."""
        with Session(self.engine) as s:
            rows = s.exec(
                select(TradeRow).where(
                    TradeRow.account_id == account_id,
                    TradeRow.action == "Sell",
                )
            ).all()
            account_display = self._account_display_for_id(s, account_id)
        return [self._row_to_trade(r, account_display) for r in rows]

    def get_buys_before_date(self, *, account_id: int, ticker: str, before_date: date) -> list[Trade]:
        """Buy trades in this account+ticker on or before `before_date`, oldest first."""
        with Session(self.engine) as s:
            rows = s.exec(
                select(TradeRow)
                .where(
                    TradeRow.account_id == account_id,
                    TradeRow.ticker == ticker,
                    TradeRow.action == "Buy",
                    TradeRow.trade_date <= before_date.isoformat(),
                )
                .order_by(TradeRow.trade_date)
            ).all()
            account_display = self._account_display_for_id(s, account_id)
        return [self._row_to_trade(r, account_display) for r in rows]

    def update_trade_basis(self, trade_id: str, cost_basis: float | None, basis_source: str) -> None:
        """Persist hydrated cost_basis and basis_source on a Trade row."""
        with Session(self.engine) as s:
            row = s.exec(select(TradeRow).where(TradeRow.id == int(trade_id))).first()
            if row is None:
                raise LookupError(f"Trade id {trade_id} not found")
            row.cost_basis = cost_basis
            row.basis_source = basis_source
            s.add(row)
            s.commit()

    def _resolve_account(self, s: Session, display: str) -> AccountRow:
        if "/" in display:
            broker, label = display.split("/", 1)
        else:
            broker, label = "Manual", display
        row = s.exec(select(AccountRow).where(AccountRow.broker == broker, AccountRow.label == label)).first()
        if row is None:
            raise LookupError(f"Account {display!r} not found — create it via /imports first")
        return row

    def create_manual_trade(self, trade: Trade, etf_pairs: dict[str, list[str]]) -> Trade:
        """Insert a user-entered trade.

        import_id is NULL; natural_key uses the 'manual:' namespace so it
        never collides with a CSV-derived key. Triggers a full wash-sale
        recompute. Returns the persisted Trade with its database id populated.
        """
        from net_alpha.engine.recompute import recompute_all_violations

        with Session(self.engine) as s:
            account = self._resolve_account(s, trade.account)
            nk = f"manual:{uuid4().hex}"
            tr = TradeRow(
                import_id=None,
                account_id=account.id,
                natural_key=nk,
                ticker=trade.ticker,
                trade_date=trade.date.isoformat(),
                action=trade.action,
                quantity=trade.quantity,
                proceeds=trade.proceeds,
                cost_basis=trade.cost_basis,
                basis_unknown=trade.basis_unknown,
                basis_source=trade.basis_source,
                option_strike=(trade.option_details.strike if trade.option_details else None),
                option_expiry=(trade.option_details.expiry.isoformat() if trade.option_details else None),
                option_call_put=(trade.option_details.call_put if trade.option_details else None),
                is_manual=True,
                transfer_basis_user_set=False,
            )
            s.add(tr)
            s.commit()
            s.refresh(tr)
            saved = self._row_to_trade(tr, self._account_display_for_id(s, tr.account_id))
        recompute_all_violations(self, etf_pairs)
        return saved

    def update_manual_trade(self, trade: Trade, etf_pairs: dict[str, list[str]]) -> Trade:
        """Update a manual trade. Verifies is_manual=True. Preserves natural_key."""
        from net_alpha.engine.recompute import recompute_all_violations

        if trade.id is None:
            raise ValueError("update_manual_trade requires Trade.id")
        with Session(self.engine) as s:
            row = s.exec(select(TradeRow).where(TradeRow.id == int(trade.id))).first()
            if row is None:
                raise LookupError(f"Trade id {trade.id} not found")
            if not row.is_manual:
                raise ValueError("update_manual_trade requires is_manual=True row")
            account = self._resolve_account(s, trade.account)
            row.account_id = account.id
            row.ticker = trade.ticker
            row.trade_date = trade.date.isoformat()
            row.action = trade.action
            row.quantity = trade.quantity
            row.proceeds = trade.proceeds
            row.cost_basis = trade.cost_basis
            row.basis_unknown = trade.basis_unknown
            row.basis_source = trade.basis_source
            row.option_strike = trade.option_details.strike if trade.option_details else None
            row.option_expiry = trade.option_details.expiry.isoformat() if trade.option_details else None
            row.option_call_put = trade.option_details.call_put if trade.option_details else None
            # is_manual stays True; natural_key untouched.
            s.add(row)
            s.commit()
            s.refresh(row)
            saved = self._row_to_trade(row, self._account_display_for_id(s, row.account_id))
        recompute_all_violations(self, etf_pairs)
        return saved

    def delete_manual_trade(self, trade_id: str, etf_pairs: dict[str, list[str]]) -> None:
        """Delete a manual trade. Verifies is_manual=True."""
        from net_alpha.engine.recompute import recompute_all_violations

        with Session(self.engine) as s:
            row = s.exec(select(TradeRow).where(TradeRow.id == int(trade_id))).first()
            if row is None:
                raise LookupError(f"Trade id {trade_id} not found")
            if not row.is_manual:
                raise ValueError("delete_manual_trade requires is_manual=True row")
            s.delete(row)
            s.commit()
        recompute_all_violations(self, etf_pairs)

    def update_imported_transfer(
        self,
        trade_id: str,
        new_date: date,
        new_basis_or_proceeds: float,
        etf_pairs: dict[str, list[str]],
    ) -> Trade:
        """Update date + basis (or proceeds) on an imported transfer row.

        Raises ValueError if the row is is_manual=True or basis_source is not
        in {'transfer_in','transfer_out'}.

        Preserves natural_key explicitly so a future re-import of the original
        CSV dedupes against the user's edit.

        Triggers a full wash-sale recompute. Returns the updated Trade.
        """
        from net_alpha.engine.recompute import recompute_all_violations

        with Session(self.engine) as s:
            row = s.exec(select(TradeRow).where(TradeRow.id == int(trade_id))).first()
            if row is None:
                raise LookupError(f"Trade id {trade_id} not found")
            if row.is_manual:
                raise ValueError("Use update_manual_trade for manual rows")
            if row.basis_source not in ("transfer_in", "transfer_out"):
                raise ValueError(f"update_imported_transfer requires a transfer row; basis_source={row.basis_source!r}")
            row.trade_date = new_date.isoformat()
            if row.basis_source == "transfer_in":
                row.cost_basis = new_basis_or_proceeds
            else:  # transfer_out
                row.proceeds = new_basis_or_proceeds
            row.transfer_basis_user_set = True
            # natural_key intentionally untouched.
            s.add(row)
            s.commit()
            s.refresh(row)
            saved = self._row_to_trade(row, self._account_display_for_id(s, row.account_id))
        recompute_all_violations(self, etf_pairs)
        return saved

    # --- Splits ---

    def add_split(
        self,
        symbol: str,
        split_date: date,
        ratio: float,
        source: str,
    ) -> int | None:
        """Insert a split. Returns the new id, or the existing id if (symbol, split_date)
        already exists (no-op for re-fetch). Returns None only on unexpected failure."""
        from datetime import UTC
        from datetime import datetime as _dt

        from net_alpha.db.tables import SplitRow

        with Session(self.engine) as s:
            existing = s.exec(
                select(SplitRow).where(
                    SplitRow.symbol == symbol,
                    SplitRow.split_date == split_date.isoformat(),
                )
            ).first()
            if existing is not None:
                return existing.id
            row = SplitRow(
                symbol=symbol,
                split_date=split_date.isoformat(),
                ratio=ratio,
                source=source,
                fetched_at=_dt.now(UTC).isoformat(),
            )
            s.add(row)
            s.commit()
            s.refresh(row)
            return row.id

    def get_splits(self, symbol: str | None = None) -> list:
        """Return all splits (optionally filtered by symbol), oldest first."""
        from datetime import datetime as _dt

        from net_alpha.db.tables import SplitRow
        from net_alpha.models.splits import Split as SplitDomain

        with Session(self.engine) as s:
            stmt = select(SplitRow)
            if symbol is not None:
                stmt = stmt.where(SplitRow.symbol == symbol)
            stmt = stmt.order_by(SplitRow.split_date)
            rows = s.exec(stmt).all()
            return [
                SplitDomain(
                    id=r.id,
                    symbol=r.symbol,
                    split_date=date.fromisoformat(r.split_date),
                    ratio=r.ratio,
                    source=r.source,
                    fetched_at=_dt.fromisoformat(r.fetched_at),
                )
                for r in rows
            ]

    # --- Lot overrides ---

    def add_lot_override(
        self,
        trade_id: int,
        field: str,
        old_value: float,
        new_value: float,
        reason: str,
        split_id: int | None = None,
    ) -> int:
        from datetime import UTC
        from datetime import datetime as _dt

        from net_alpha.db.tables import LotOverrideRow

        with Session(self.engine) as s:
            row = LotOverrideRow(
                trade_id=trade_id,
                field=field,
                old_value=old_value,
                new_value=new_value,
                reason=reason,
                split_id=split_id,
                edited_at=_dt.now(UTC).isoformat(),
            )
            s.add(row)
            s.commit()
            s.refresh(row)
            return row.id

    def get_lot_overrides_for_trade(self, trade_id: int) -> list:
        from datetime import datetime as _dt

        from net_alpha.db.tables import LotOverrideRow
        from net_alpha.models.splits import LotOverride

        with Session(self.engine) as s:
            rows = s.exec(
                select(LotOverrideRow).where(LotOverrideRow.trade_id == trade_id).order_by(LotOverrideRow.edited_at)
            ).all()
            return [
                LotOverride(
                    id=r.id,
                    trade_id=r.trade_id,
                    field=r.field,
                    old_value=r.old_value,
                    new_value=r.new_value,
                    reason=r.reason,
                    edited_at=_dt.fromisoformat(r.edited_at),
                    split_id=r.split_id,
                )
                for r in rows
            ]

    def all_lot_overrides(self) -> list:
        """All overrides across all trades, used by the post-recompute applier."""
        from datetime import datetime as _dt

        from net_alpha.db.tables import LotOverrideRow
        from net_alpha.models.splits import LotOverride

        with Session(self.engine) as s:
            rows = s.exec(select(LotOverrideRow).order_by(LotOverrideRow.edited_at)).all()
            return [
                LotOverride(
                    id=r.id,
                    trade_id=r.trade_id,
                    field=r.field,
                    old_value=r.old_value,
                    new_value=r.new_value,
                    reason=r.reason,
                    edited_at=_dt.fromisoformat(r.edited_at),
                    split_id=r.split_id,
                )
                for r in rows
            ]

    def get_split_overrides_for_trade(self, trade_id: int, split_id: int) -> list:
        """Used by apply_split to check idempotency: 'have I already applied this split to this trade?'"""
        from net_alpha.db.tables import LotOverrideRow

        with Session(self.engine) as s:
            rows = s.exec(
                select(LotOverrideRow).where(
                    LotOverrideRow.trade_id == trade_id,
                    LotOverrideRow.split_id == split_id,
                )
            ).all()
            return list(rows)

    def get_lot_rows_for_symbol(self, symbol: str) -> list:
        """Return raw LotRow records (NOT domain Lot) so the splits applier
        can mutate them by id. Open-only is the default since closed lots are
        irrelevant to the user's current holdings; for split application we
        also want closed lots so historical wash-sale data stays correct."""
        from net_alpha.db.tables import LotRow

        with Session(self.engine) as s:
            rows = s.exec(select(LotRow).where(LotRow.ticker == symbol)).all()
            # Detach from session by copying to dicts; caller will mutate via update_lot_qty_and_basis.
            return [
                {
                    "id": r.id,
                    "trade_id": r.trade_id,
                    "ticker": r.ticker,
                    "trade_date": r.trade_date,
                    "quantity": r.quantity,
                    "adjusted_basis": r.adjusted_basis,
                    "cost_basis": r.cost_basis,
                }
                for r in rows
            ]

    def update_lot_qty_and_basis(self, lot_id: int, *, quantity: float, adjusted_basis: float) -> None:
        from net_alpha.db.tables import LotRow

        with Session(self.engine) as s:
            row = s.get(LotRow, lot_id)
            if row is None:
                return
            row.quantity = quantity
            row.adjusted_basis = adjusted_basis
            s.add(row)
            s.commit()


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
