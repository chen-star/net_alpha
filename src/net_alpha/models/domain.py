from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from pydantic import BaseModel, Field


class OptionDetails(BaseModel):
    """Option contract details parsed from symbol string."""

    strike: float
    expiry: date
    call_put: str  # "C" or "P"


class CashEvent(BaseModel):
    """A non-trade cash movement (transfer, dividend, interest, fee, sweep)."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    account: str
    event_date: date
    kind: str  # transfer_in | transfer_out | dividend | interest | fee | sweep_in | sweep_out
    amount: float  # always positive; sign comes from `kind`
    ticker: str | None = None
    description: str = ""

    def compute_natural_key(self) -> str:
        """SHA256 over canonical fields used for idempotent re-import dedup."""
        import hashlib

        payload = "|".join(
            [
                self.account,
                self.event_date.isoformat(),
                self.kind,
                f"{self.amount:.6f}",
                self.ticker or "",
                self.description,
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class Trade(BaseModel):
    """A single trade (buy or sell) from a broker CSV."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    account: str
    date: date
    ticker: str
    action: str  # "Buy" or "Sell"
    quantity: float
    proceeds: float | None = None
    cost_basis: float | None = None
    basis_unknown: bool = False
    basis_source: str = "unknown"
    is_manual: bool = False
    transfer_basis_user_set: bool = False
    gross_cash_impact: float | None = None
    option_details: OptionDetails | None = None
    # Original broker-statement date for transfer rows. ``date`` (above) holds
    # the *acquisition* date — initially the same as the broker date but
    # rewritten by the user once they look up when the lot was acquired.
    # Storing both lets the timeline render "Acq … · Xferred …" so the
    # broker date is preserved as audit context. Null on non-transfer rows.
    transfer_date: date | None = None
    # Groups sibling rows produced by splitting one transfer into N
    # acquisition lots (multi-segment). All siblings share this id and the
    # same ``transfer_date``. Null on un-split rows.
    transfer_group_id: str | None = None
    raw_row_hash: str | None = None
    schema_cache_id: str | None = None
    # Within-CSV occurrence index for trades whose canonical fields are
    # genuinely duplicated (Schwab can split a fill across two identical
    # rows on the same day at the same price). Set by the parser based on
    # how many prior identical trades it has seen in the same file. The
    # natural-key formula folds this in only when > 0, so single-occurrence
    # rows keep the legacy key and existing DB rows continue to dedup
    # against re-imports.
    occurrence_index: int = 0
    is_section_1256: bool = False

    def is_buy(self) -> bool:
        return self.action.lower() == "buy"

    def is_sell(self) -> bool:
        return self.action.lower() == "sell"

    def is_option(self) -> bool:
        return self.option_details is not None

    def is_loss(self) -> bool:
        if not self.is_sell() or self.basis_unknown:
            return False
        if self.proceeds is not None and self.cost_basis is not None:
            return self.proceeds < self.cost_basis
        return False

    def loss_amount(self) -> float:
        if self.is_loss() and self.proceeds is not None and self.cost_basis is not None:
            return self.cost_basis - self.proceeds
        return 0.0

    def compute_natural_key(self) -> str:
        """SHA256 over canonical fields used for idempotent re-import dedup."""
        import hashlib

        opt = ""
        if self.option_details is not None:
            o = self.option_details
            opt = f"{o.strike}|{o.expiry.isoformat()}|{o.call_put}"
        payload = "|".join(
            [
                self.account,
                self.date.isoformat(),
                self.ticker,
                self.action,
                str(self.quantity),
                str(self.proceeds if self.proceeds is not None else ""),
                str(self.cost_basis if self.cost_basis is not None else ""),
                opt,
            ]
        )
        # Append the occurrence-index suffix only when > 0 so first-occurrence
        # rows keep the legacy key (existing DB rows dedup correctly on re-import).
        if self.occurrence_index > 0:
            payload = payload + f"|occ{self.occurrence_index}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ImportResult(BaseModel):
    """Result of parsing one broker CSV: trades + cash events + warnings."""

    trades: list[Trade] = Field(default_factory=list)
    cash_events: list[CashEvent] = Field(default_factory=list)
    parse_warnings: list[str] = Field(default_factory=list)


class Lot(BaseModel):
    """A buy lot with adjustable cost basis for wash sale tracking."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    trade_id: str
    account: str
    date: date
    ticker: str
    quantity: float
    cost_basis: float
    adjusted_basis: float
    option_details: OptionDetails | None = None

    @classmethod
    def from_trade(cls, trade: Trade) -> Lot:
        return cls(
            trade_id=trade.id,
            account=trade.account,
            date=trade.date,
            ticker=trade.ticker,
            quantity=trade.quantity,
            cost_basis=trade.cost_basis or 0.0,
            adjusted_basis=trade.cost_basis or 0.0,
            option_details=trade.option_details,
        )


class WashSaleViolation(BaseModel):
    """A detected wash sale linking a loss sale to its triggering replacement."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    loss_trade_id: str
    replacement_trade_id: str
    confidence: str  # "Confirmed", "Probable", or "Unclear"
    disallowed_loss: float
    matched_quantity: float
    loss_account: str = ""
    buy_account: str = ""
    loss_sale_date: date | None = None
    triggering_buy_date: date | None = None
    ticker: str = ""
    source: str = "engine"  # "schwab_g_l" | "engine"


class ExemptMatch(BaseModel):
    """A would-have-been wash-sale that's exempt under a named rule (e.g., §1256)."""

    loss_trade_id: str
    triggering_buy_id: str
    exempt_reason: str  # enum: "section_1256" (extensible)
    rule_citation: str  # e.g., "IRC §1256(c)"
    notional_disallowed: Decimal
    confidence: str
    matched_quantity: float
    loss_account: str
    buy_account: str
    loss_sale_date: date
    triggering_buy_date: date
    ticker: str


class Section1256Classification(BaseModel):
    """60/40 LT/ST split for a closed §1256 contract trade. Statutory under §1256(a)(3)."""

    trade_id: str
    realized_pnl: Decimal
    long_term_portion: Decimal
    short_term_portion: Decimal
    underlying: str


class DetectionResult(BaseModel):
    """Output of the wash sale detection engine."""

    violations: list[WashSaleViolation]
    lots: list[Lot]
    basis_unknown_count: int = 0
    exempt_matches: list[ExemptMatch] = []  # NEW


# v2 additions ----------------------------------------------------------------


class Account(BaseModel):
    """A user-named account scoped to a single broker."""

    id: int | None = None
    broker: str
    label: str

    def display(self) -> str:
        return f"{self.broker}/{self.label}"


class ImportRecord(BaseModel):
    """Metadata for one CSV import. Trades hold a FK to this."""

    id: int | None = None
    account_id: int
    csv_filename: str
    csv_sha256: str
    imported_at: datetime
    trade_count: int
    # v4 additions — optional; populated by import path or backfill.
    min_trade_date: date | None = None
    max_trade_date: date | None = None
    equity_count: int | None = None
    option_count: int | None = None
    option_expiry_count: int | None = None
    parse_warnings: list[str] = Field(default_factory=list)
    # v5 — count of natural-key duplicates the upload route filtered out before
    # add_import got the trade list. Persisted so the imports page can render
    # "imported 0 trades · skipped 7 duplicates" instead of "no records".
    duplicate_trades: int = 0


class AddImportResult(BaseModel):
    import_id: int
    new_trades: int
    duplicate_trades: int
    new_cash_events: int = 0


class RemoveImportResult(BaseModel):
    removed_trade_count: int
    recompute_window: tuple[date, date] | None = None


class ImportSummary(BaseModel):
    """Display row for `net-alpha imports`."""

    id: int
    account_display: str
    csv_filename: str
    trade_count: int
    imported_at: datetime
    gl_lot_count: int = 0
    # v4 additions; None means "not yet aggregated" (rendered as em-dash).
    min_trade_date: date | None = None
    max_trade_date: date | None = None
    equity_count: int | None = None
    option_count: int | None = None
    option_expiry_count: int | None = None
    parse_warnings: list[str] = Field(default_factory=list)
    duplicate_trades: int = 0
    cash_event_count: int = 0


class LotConsumption(BaseModel):
    """One lot consumed (partially or fully) by a hypothetical sell."""

    lot_id: int
    quantity: Decimal
    basis_per_share: Decimal
    purchase_date: date


class SimulationOption(BaseModel):
    """One scenario in `sim`'s output: 'sell from this account'."""

    account: Account
    lots_consumed_fifo: list[LotConsumption]
    realized_pnl: Decimal
    would_trigger_wash_sale: bool
    blocking_buys: list[Trade]
    lookforward_block_until: date | None
    confidence: str  # "Confirmed" | "Probable" | "Unclear" | "N/A"
    insufficient_shares: bool
    available_shares: Decimal


class SimBuyMatch(BaseModel):
    """One pre-existing loss sale that the proposed buy would wash-trigger."""

    loss_trade_id: str
    loss_sale_date: date
    loss_account: str
    loss_ticker: str
    matched_quantity: Decimal
    disallowed_loss: Decimal
    confidence: str  # "Confirmed" | "Probable" | "Unclear"


class SimulationBuyOption(BaseModel):
    """One scenario in `sim`'s buy output: 'buy in this account'."""

    account: Account
    matches: list[SimBuyMatch]
    total_disallowed: Decimal
    proposed_basis: Decimal  # qty * price (raw cost basis pre-adjustment)
    adjusted_basis: Decimal  # proposed_basis + total_disallowed
    clean: bool  # True iff matches == []
