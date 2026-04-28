# src/net_alpha/db/tables.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class AccountRow(SQLModel, table=True):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("broker", "label", name="uq_account_broker_label"),)

    id: int | None = Field(default=None, primary_key=True)
    broker: str = Field(index=True)
    label: str = Field(index=True)


class ImportRecordRow(SQLModel, table=True):
    __tablename__ = "imports"

    id: int | None = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="accounts.id", index=True)
    csv_filename: str
    csv_sha256: str = Field(index=True)
    imported_at: datetime
    trade_count: int

    # v4 additions — populated on import or backfilled at startup.
    min_trade_date: str | None = None
    max_trade_date: str | None = None
    equity_count: int | None = None
    option_count: int | None = None
    option_expiry_count: int | None = None
    parse_warnings_json: str | None = None  # JSON-encoded list[str]; "[]" = no warnings
    # v5 — count of trades dropped as natural-key duplicates of prior imports.
    # Nullable (defaults to 0 in Python) so legacy raw-SQL inserts in old tests
    # that omit the column don't fail; the migration also stamps a DB DEFAULT 0
    # so existing v4 rows read back as 0 not NULL.
    duplicate_trades: int | None = Field(default=0)
    cash_event_count: int | None = Field(default=0)


class TradeRow(SQLModel, table=True):
    __tablename__ = "trades"
    __table_args__ = (UniqueConstraint("account_id", "natural_key", name="uq_trade_account_natkey"),)

    id: int | None = Field(default=None, primary_key=True)
    import_id: int | None = Field(default=None, foreign_key="imports.id", index=True)
    account_id: int = Field(foreign_key="accounts.id", index=True)
    natural_key: str = Field(index=True)

    ticker: str = Field(index=True)
    trade_date: str = Field(index=True)  # YYYY-MM-DD as-is from broker
    action: str
    quantity: float
    proceeds: float | None = None
    cost_basis: float | None = None
    basis_unknown: bool = False

    option_strike: float | None = None
    option_expiry: str | None = None
    option_call_put: str | None = None
    basis_source: str = Field(default="unknown")
    # values: "broker_csv" | "g_l" | "fifo" | "unknown" | "user"
    is_manual: bool = Field(default=False)
    transfer_basis_user_set: bool = Field(default=False)
    gross_cash_impact: float | None = Field(default=None)
    # The original broker-statement date the transfer landed in the account.
    # ``trade_date`` (above) is the *acquisition* date — set initially to the
    # broker date but rewritten by the user once they look up the lot's
    # acquisition history. Storing both lets the timeline show "Acq …
    # · Xferred …" so the user can audit when the shares actually moved
    # vs when the cost basis began. Only meaningful when basis_source is in
    # {'transfer_in','transfer_out'}; null otherwise.
    transfer_date: str | None = Field(default=None)
    # Groups sibling rows that came from a single multi-segment transfer split
    # (one transfer with N acquisition lots). All siblings share the same
    # transfer_group_id and the same transfer_date. Null for un-split rows.
    transfer_group_id: str | None = Field(default=None, index=True)


class LotRow(SQLModel, table=True):
    __tablename__ = "lots"

    id: int | None = Field(default=None, primary_key=True)
    trade_id: int = Field(foreign_key="trades.id", index=True)
    account_id: int = Field(foreign_key="accounts.id", index=True)

    ticker: str = Field(index=True)
    trade_date: str
    quantity: float
    cost_basis: float
    adjusted_basis: float

    option_strike: float | None = None
    option_expiry: str | None = None
    option_call_put: str | None = None


class WashSaleViolationRow(SQLModel, table=True):
    __tablename__ = "wash_sale_violations"

    id: int | None = Field(default=None, primary_key=True)
    loss_trade_id: int = Field(foreign_key="trades.id", index=True)
    replacement_trade_id: int = Field(foreign_key="trades.id", index=True)
    loss_account_id: int = Field(foreign_key="accounts.id", index=True)
    buy_account_id: int = Field(foreign_key="accounts.id", index=True)
    loss_sale_date: str = Field(index=True)
    triggering_buy_date: str = Field(index=True)
    ticker: str = Field(index=True, default="")
    confidence: str
    disallowed_loss: float
    matched_quantity: float
    source: str = Field(default="engine")
    # values: "schwab_g_l" | "engine"


class MetaRow(SQLModel, table=True):
    __tablename__ = "meta"

    key: str = Field(primary_key=True)
    value: str


class RealizedGLLotRow(SQLModel, table=True):
    __tablename__ = "realized_gl_lots"

    id: int | None = Field(default=None, primary_key=True)
    import_id: int = Field(foreign_key="imports.id", index=True)
    account_id: int = Field(foreign_key="accounts.id", index=True)

    symbol_raw: str = Field(index=True)
    ticker: str = Field(index=True)
    closed_date: str = Field(index=True)
    opened_date: str
    quantity: float
    proceeds: float
    cost_basis: float
    unadjusted_cost_basis: float
    wash_sale: bool
    disallowed_loss: float
    term: str

    option_strike: float | None = None
    option_expiry: str | None = None
    option_call_put: str | None = None

    natural_key: str = Field(unique=True, index=True)


class PriceCacheRow(SQLModel, table=True):
    __tablename__ = "price_cache"

    symbol: str = Field(primary_key=True)
    price: float
    as_of: str  # ISO 8601 timestamp from provider
    fetched_at: str  # ISO 8601 UTC timestamp; TTL check performed by cache.py
    source: str  # e.g. "yahoo"


class SplitRow(SQLModel, table=True):
    __tablename__ = "splits"
    __table_args__ = (UniqueConstraint("symbol", "split_date", name="uq_splits_symbol_date"),)

    id: int | None = Field(default=None, primary_key=True)
    symbol: str = Field(index=True)
    split_date: str  # YYYY-MM-DD ex-date
    ratio: float  # new shares ÷ old shares; 2.0 = 2-for-1; 0.1 = 1-for-10 reverse
    source: str  # 'yahoo' | 'manual'
    fetched_at: str  # ISO 8601 UTC timestamp


class LotOverrideRow(SQLModel, table=True):
    __tablename__ = "lot_overrides"

    id: int | None = Field(default=None, primary_key=True)
    trade_id: int = Field(foreign_key="trades.id", index=True)
    field: str  # 'quantity' | 'adjusted_basis'
    old_value: float
    new_value: float
    reason: str  # 'split' | 'manual' | 'transfer_basis_fix'
    edited_at: str  # ISO 8601 UTC timestamp
    split_id: int | None = Field(default=None, foreign_key="splits.id", index=True)
    # split_id is set when reason='split'; lets apply_split check idempotency.


class CashEventRow(SQLModel, table=True):
    __tablename__ = "cash_events"
    __table_args__ = (UniqueConstraint("account_id", "natural_key", name="uq_cash_event_account_natkey"),)

    id: int | None = Field(default=None, primary_key=True)
    import_id: int = Field(foreign_key="imports.id", index=True)
    account_id: int = Field(foreign_key="accounts.id", index=True)
    natural_key: str = Field(index=True)

    event_date: str = Field(index=True)  # YYYY-MM-DD as-is from broker
    kind: str  # transfer_in | transfer_out | dividend | interest | fee | sweep_in | sweep_out
    amount: float  # always positive; sign comes from `kind`
    ticker: str | None = Field(default=None, index=True)
    description: str = ""


class UserPreferenceRow(SQLModel, table=True):
    __tablename__ = "user_preferences"

    account_id: int = Field(primary_key=True, foreign_key="accounts.id")
    profile: str = Field(default="active")  # 'conservative' | 'active' | 'options'
    density: str = Field(default="comfortable")  # 'compact' | 'comfortable' | 'tax'
    updated_at: datetime
