"""Domain models for stock splits and lot overrides."""

from __future__ import annotations

from datetime import date as _date
from datetime import datetime

from pydantic import BaseModel


class Split(BaseModel):
    id: int
    symbol: str
    split_date: _date
    ratio: float
    source: str  # 'yahoo' | 'manual'
    fetched_at: datetime


class LotOverride(BaseModel):
    id: int
    trade_id: int
    field: str  # 'quantity' | 'adjusted_basis'
    old_value: float
    new_value: float
    reason: str  # 'split' | 'manual' | 'transfer_basis_fix'
    edited_at: datetime
    split_id: int | None = None
