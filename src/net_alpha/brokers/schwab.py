# src/net_alpha/brokers/schwab.py
from __future__ import annotations

from datetime import datetime

from net_alpha.ingest.option_parser import parse_option_symbol
from net_alpha.models.domain import Trade

# Schwab buy actions (v1 KNOWN_BROKER_SCHEMAS: "Buy", "Reinvest"; also options: "Buy to Open")
_BUY_ACTIONS = {"Buy", "Reinvest Shares", "Reinvest", "Buy to Open"}
# Schwab sell actions (v1: "Sell"; also options: "Sell to Close")
_SELL_ACTIONS = {"Sell", "Sell to Close"}


class SchwabParser:
    name = "schwab"
    REQUIRED_HEADERS = {"Date", "Action", "Symbol", "Quantity", "Amount"}

    def detect(self, headers: list[str]) -> bool:
        return self.REQUIRED_HEADERS.issubset(set(headers))

    def parse(self, rows: list[dict[str, str]], account_display: str) -> list[Trade]:
        trades: list[Trade] = []
        for i, row in enumerate(rows, start=1):
            action_raw = row["Action"].strip()

            if action_raw in _BUY_ACTIONS:
                action = "Buy"
            elif action_raw in _SELL_ACTIONS:
                action = "Sell"
            else:
                # Non-trade rows (Cash Dividend, Journal, Wire Transferred, etc.) — skip
                continue

            try:
                trade_date = datetime.strptime(row["Date"].strip()[:10], "%m/%d/%Y").date()
            except ValueError as e:
                raise ValueError(
                    f"Row {i}: 'Date' value {row['Date']!r} is not a valid date"
                ) from e

            symbol = row["Symbol"].strip()
            opt = parse_option_symbol(symbol)
            ticker = opt[0] if opt else symbol

            qty_raw = row["Quantity"].replace(",", "").strip()
            amount_raw = row["Amount"].replace("$", "").replace(",", "").strip()

            try:
                qty = float(qty_raw) if qty_raw else 0.0
            except ValueError as e:
                raise ValueError(f"Row {i}: 'Quantity' value {row['Quantity']!r} is not numeric") from e

            try:
                amount = float(amount_raw) if amount_raw else 0.0
            except ValueError as e:
                raise ValueError(f"Row {i}: 'Amount' value {row['Amount']!r} is not numeric") from e

            cost_basis = abs(amount) if action == "Buy" else None
            proceeds = abs(amount) if action == "Sell" else None

            trades.append(
                Trade(
                    account=account_display,
                    date=trade_date,
                    ticker=ticker,
                    action=action,
                    quantity=qty,
                    proceeds=proceeds,
                    cost_basis=cost_basis,
                    option_details=opt[1] if opt else None,
                )
            )
        return trades
