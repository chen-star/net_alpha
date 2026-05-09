# src/net_alpha/brokers/robinhood.py
from __future__ import annotations

from datetime import date, datetime

from net_alpha.ingest.option_parser import parse_option_symbol
from net_alpha.models.domain import ImportResult, Trade


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


_BUY_CODES = {"Buy", "BTO"}
_SELL_CODES = {"Sell", "STC"}
_SHORT_OPTION_OPEN_CODES = {"STO"}
_SHORT_OPTION_CLOSE_CODES = {"BTC"}
_NON_TRADE_KNOWN_CODES = {"OEXP"}


class RobinhoodParser:
    name = "robinhood"
    REQUIRED_HEADERS = {"Activity Date", "Trans Code", "Instrument", "Quantity", "Amount"}

    def detect(self, headers: list[str]) -> bool:
        return self.REQUIRED_HEADERS.issubset(set(headers))

    def parse(self, rows: list[dict[str, str]], account_display: str) -> list[Trade]:
        trades: list[Trade] = []
        for i, row in enumerate(rows, start=1):
            code = row.get("Trans Code", "").strip()
            short_open = False
            short_close = False
            if code in _BUY_CODES:
                action = "Buy"
            elif code in _SELL_CODES:
                action = "Sell"
            elif code in _SHORT_OPTION_OPEN_CODES:
                action = "Sell"
                short_open = True
            elif code in _SHORT_OPTION_CLOSE_CODES:
                action = "Buy"
                short_close = True
            elif code in _NON_TRADE_KNOWN_CODES:
                continue
            else:
                continue

            try:
                trade_date = datetime.strptime(row["Activity Date"].strip()[:10], "%m/%d/%Y").date()
            except ValueError as e:
                raise ValueError(
                    f"Row {i}: 'Activity Date' value {row['Activity Date']!r} is not a valid date"
                ) from e

            symbol = row["Instrument"].strip()
            opt = parse_option_symbol(symbol)
            ticker = opt[0] if opt else symbol

            qty = _qty(row.get("Quantity", ""))
            amount = _money(row.get("Amount", ""))

            cost_basis = abs(amount) if action == "Buy" else None
            proceeds = abs(amount) if action == "Sell" else None

            basis_source: str | None = None
            if short_open:
                basis_source = "option_short_open"
            elif short_close:
                basis_source = "option_short_close"

            kwargs: dict[str, object] = {
                "account": account_display,
                "date": trade_date,
                "ticker": ticker,
                "action": action,
                "quantity": qty,
                "proceeds": proceeds,
                "cost_basis": cost_basis,
                "option_details": opt[1] if opt else None,
                "gross_cash_impact": amount,
            }
            if basis_source is not None:
                kwargs["basis_source"] = basis_source
            trades.append(Trade(**kwargs))

        seen: dict[str, int] = {}
        for t in trades:
            base = t.compute_natural_key()
            seen[base] = seen.get(base, -1) + 1
            if seen[base] > 0:
                t.occurrence_index = seen[base]
        return trades

    def parse_full(self, rows: list[dict[str, str]], account_display: str) -> ImportResult:
        return ImportResult(trades=self.parse(rows, account_display), cash_events=[], parse_warnings=[])
