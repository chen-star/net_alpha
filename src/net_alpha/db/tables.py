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


class TradeRow(SQLModel, table=True):
    __tablename__ = "trades"
    __table_args__ = (UniqueConstraint("account_id", "natural_key", name="uq_trade_account_natkey"),)

    id: int | None = Field(default=None, primary_key=True)
    import_id: int = Field(foreign_key="imports.id", index=True)
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
    # values: "broker_csv" | "g_l" | "fifo" | "unknown"


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
    as_of: str        # ISO 8601 timestamp from provider
    fetched_at: str   # ISO 8601 UTC timestamp; TTL check performed by cache.py
    source: str       # e.g. "yahoo"
