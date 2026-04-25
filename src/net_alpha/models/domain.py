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
    option_details: OptionDetails | None = None
    raw_row_hash: str | None = None
    schema_cache_id: str | None = None

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
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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


class DetectionResult(BaseModel):
    """Output of the wash sale detection engine."""

    violations: list[WashSaleViolation]
    lots: list[Lot]
    basis_unknown_count: int


class RealizedPair(BaseModel):
    """A sell matched to a specific buy lot with quantity consumed."""

    sell_trade_id: str
    buy_lot_date: date
    buy_lot_account: str
    quantity: float
    proceeds: float
    basis: float
    basis_unknown: bool
    is_long_term: bool  # holding period > 365 days


class OpenLot(BaseModel):
    """An open (unconsumed) buy lot with holding period info."""

    ticker: str
    account: str
    quantity: float
    adjusted_basis_per_share: float
    purchase_date: date
    days_held: int
    days_to_long_term: int  # 0 if already long-term
    basis_unknown: bool
    is_option: bool


class AllocationResult(BaseModel):
    """Output of _allocate_lots — shared by tax position and open lots."""

    realized_pairs: list[RealizedPair]
    open_lots: list[OpenLot]


class TaxPosition(BaseModel):
    """YTD realized tax position with ST/LT classification."""

    st_gains: float
    st_losses: float
    lt_gains: float
    lt_losses: float
    year: int
    basis_unknown_count: int

    @property
    def net_st(self) -> float:
        return self.st_gains - self.st_losses

    @property
    def net_lt(self) -> float:
        return self.lt_gains - self.lt_losses

    @property
    def net_capital_gain(self) -> float:
        return self.net_st + self.net_lt

    @property
    def loss_needed_to_zero_st(self) -> float:
        return max(0.0, self.net_st)

    @property
    def carryforward(self) -> float:
        return max(0.0, -self.net_capital_gain - 3000.0)


class LotSelection(BaseModel):
    """Result of applying a lot selection method (FIFO/HIFO/LIFO) to a sell."""

    method: str  # "FIFO", "HIFO", "LIFO"
    lots_used: list[OpenLot]
    st_gain_loss: float
    lt_gain_loss: float
    total_gain_loss: float
    wash_sale_risk: bool


class LotRecommendation(BaseModel):
    """Structured recommendation from the lot selection decision tree."""

    preferred_method: str  # "FIFO", "HIFO", "LIFO"
    reason: str  # "st_loss_offset", "lt_lower_rate", "least_gain"
    has_wash_risk: bool
    safe_sell_date: date | None
    fallback_method: str | None
    fallback_reason: str | None


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


class AddImportResult(BaseModel):
    import_id: int
    new_trades: int
    duplicate_trades: int


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
