# src/net_alpha/db/tables.py
from __future__ import annotations

from sqlmodel import Field, SQLModel


class TradeRow(SQLModel, table=True):
    __tablename__ = "trades"

    id: str = Field(primary_key=True)
    account: str = Field(index=True)
    date: str = Field(index=True)  # YYYY-MM-DD
    ticker: str = Field(index=True)
    action: str
    quantity: float
    proceeds: float | None = None
    cost_basis: float | None = None
    basis_unknown: bool = False
    raw_row_hash: str | None = Field(default=None, index=True)
    schema_cache_id: str | None = Field(default=None)

    # Option fields (flattened — no nested tables)
    option_strike: float | None = None
    option_expiry: str | None = None  # YYYY-MM-DD
    option_call_put: str | None = None  # "C" or "P"


class LotRow(SQLModel, table=True):
    __tablename__ = "lots"

    id: str = Field(primary_key=True)
    trade_id: str = Field(index=True)
    account: str
    date: str
    ticker: str = Field(index=True)
    quantity: float
    cost_basis: float
    adjusted_basis: float

    option_strike: float | None = None
    option_expiry: str | None = None
    option_call_put: str | None = None


class WashSaleViolationRow(SQLModel, table=True):
    __tablename__ = "wash_sale_violations"

    id: str = Field(primary_key=True)
    loss_trade_id: str = Field(index=True)
    replacement_trade_id: str = Field(index=True)
    confidence: str
    disallowed_loss: float
    matched_quantity: float


class SchemaCacheRow(SQLModel, table=True):
    __tablename__ = "schema_cache"

    id: str = Field(primary_key=True)
    broker_name: str = Field(index=True)
    header_hash: str = Field(index=True)
    column_mapping: str  # JSON string
    option_format: str | None = None


class MetaRow(SQLModel, table=True):
    __tablename__ = "meta"

    key: str = Field(primary_key=True)
    value: str
