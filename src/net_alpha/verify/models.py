"""SQLModel rows for the verification engine.

Tables:
  verify_result   — one row per L2 background-job run
  verify_finding  — one row per failed/warned check within a run
  broker_position — parsed Schwab All-Positions CSV rows
"""

from __future__ import annotations

from sqlmodel import Field, SQLModel


class VerifyResult(SQLModel, table=True):
    __tablename__ = "verify_result"

    id: int | None = Field(default=None, primary_key=True)
    run_at: str  # ISO timestamp
    trigger: str  # "scheduled" | "trade_import" | "positions_import" | "manual"
    status: str  # "ok" | "warn" | "fail" | "stale"
    duration_ms: int
    checks_total: int
    checks_passed: int
    checks_warned: int
    checks_failed: int
    reference_age_days: int | None = None
    notes: str | None = None


class VerifyFinding(SQLModel, table=True):
    __tablename__ = "verify_finding"

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="verify_result.id")
    rule_id: str  # e.g. "OV-1", "RealizedRecon", "BasisRecon"
    severity: str  # "warn" | "fail" | "stale"
    scope: str  # e.g. "AAPL/IRA-Roth" or "global"
    ours: float | None = None
    theirs: float | None = None
    delta: float | None = None
    detail_json: str | None = None


class BrokerPosition(SQLModel, table=True):
    __tablename__ = "broker_position"

    id: int | None = Field(default=None, primary_key=True)
    import_id: int = Field(foreign_key="imports.id")
    account_label: str
    symbol: str
    qty: float
    cost_basis: float
    market_value: float
    unrealized_pl: float
    as_of_date: str  # YYYY-MM-DD from CSV header
