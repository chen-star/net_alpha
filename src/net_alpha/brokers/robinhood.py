# src/net_alpha/brokers/robinhood.py
from __future__ import annotations

from datetime import date, datetime

from net_alpha.ingest.option_parser import parse_option_symbol  # noqa: F401
from net_alpha.models.domain import CashEvent, ImportResult, Trade  # noqa: F401


def _money(s: str) -> float:
    s = s.replace("$", "").replace(",", "").strip()
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _qty(s: str) -> float:
    s = s.replace(",", "").strip()
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _parse_date(s: str) -> date | None:
    try:
        return datetime.strptime(s.strip()[:10], "%m/%d/%Y").date()
    except ValueError:
        return None


class RobinhoodParser:
    name = "robinhood"
    REQUIRED_HEADERS = {"Activity Date", "Trans Code", "Instrument", "Quantity", "Amount"}

    def detect(self, headers: list[str]) -> bool:
        return self.REQUIRED_HEADERS.issubset(set(headers))

    def parse(self, rows: list[dict[str, str]], account_display: str) -> list[Trade]:
        return []

    def parse_full(self, rows: list[dict[str, str]], account_display: str) -> ImportResult:
        return ImportResult(trades=[], cash_events=[], parse_warnings=[])
