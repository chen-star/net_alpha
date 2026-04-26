from __future__ import annotations

from datetime import datetime

from net_alpha.ingest.option_parser import parse_option_symbol
from net_alpha.models.realized_gl import RealizedGLLot


def _parse_money(s: str) -> float:
    """'$330.33' or '-$130.33' or '' → float (0.0 when empty)."""
    s = s.strip().replace("$", "").replace(",", "")
    if not s:
        return 0.0
    return float(s)


def _parse_yes_no(s: str) -> bool:
    return s.strip().lower() == "yes"


def _parse_mdy(s: str) -> datetime:
    return datetime.strptime(s.strip(), "%m/%d/%Y")


class SchwabRealizedGLParser:
    name = "schwab_realized_gl"
    REQUIRED_HEADERS = {
        "Symbol",
        "Closed Date",
        "Opened Date",
        "Quantity",
        "Proceeds",
        "Cost Basis (CB)",
        "Wash Sale?",
    }

    def detect(self, headers: list[str]) -> bool:
        return self.REQUIRED_HEADERS.issubset(set(headers))

    def parse(self, rows: list[dict[str, str]], account_display: str) -> list[RealizedGLLot]:
        out: list[RealizedGLLot] = []
        for i, row in enumerate(rows, start=1):
            symbol_raw = row["Symbol"].strip()
            if not symbol_raw:
                continue  # skip blank/total rows

            try:
                closed_date = _parse_mdy(row["Closed Date"]).date()
                opened_date = _parse_mdy(row["Opened Date"]).date()
            except ValueError as e:
                raise ValueError(f"Row {i}: invalid date in 'Closed Date' or 'Opened Date': {e}") from e

            try:
                qty = float(row["Quantity"].strip().replace(",", ""))
            except ValueError as e:
                raise ValueError(f"Row {i}: 'Quantity' value {row['Quantity']!r} is not numeric") from e

            proceeds = _parse_money(row["Proceeds"])
            cost_basis = _parse_money(row["Cost Basis (CB)"])
            unadjusted = _parse_money(row.get("Unadjusted Cost Basis", "") or row["Cost Basis (CB)"])

            wash_sale = _parse_yes_no(row["Wash Sale?"])
            disallowed = _parse_money(row.get("Disallowed Loss", ""))

            term = row.get("Term", "").strip()

            opt = parse_option_symbol(symbol_raw)
            ticker = opt[0] if opt else symbol_raw
            opt_strike = opt[1].strike if opt else None
            opt_expiry = opt[1].expiry.isoformat() if opt else None
            opt_cp = opt[1].call_put if opt else None

            out.append(
                RealizedGLLot(
                    account_display=account_display,
                    symbol_raw=symbol_raw,
                    ticker=ticker,
                    closed_date=closed_date,
                    opened_date=opened_date,
                    quantity=qty,
                    proceeds=proceeds,
                    cost_basis=cost_basis,
                    unadjusted_cost_basis=unadjusted,
                    wash_sale=wash_sale,
                    disallowed_loss=disallowed,
                    term=term,
                    option_strike=opt_strike,
                    option_expiry=opt_expiry,
                    option_call_put=opt_cp,
                )
            )
        return out
