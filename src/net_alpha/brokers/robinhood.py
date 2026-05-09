# src/net_alpha/brokers/robinhood.py
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime

from net_alpha.ingest.option_parser import parse_option_symbol
from net_alpha.models.domain import CashEvent, ImportResult, Trade


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
_NON_TRADE_KNOWN_CODES = {"OEXP", "OASGN"}
_TRANSFER_CODES = {"REC"}

# Codes the trade-side `parse(...)` already handles. Used by parse_full(...)
# to skip these in its own row walk (they're already in `trades`).
_TRADE_SIDE_CODES = (
    _BUY_CODES | _SELL_CODES
    | _SHORT_OPTION_OPEN_CODES | _SHORT_OPTION_CLOSE_CODES
    | _NON_TRADE_KNOWN_CODES | _TRANSFER_CODES
)

# Codes that are known but not trades and not cash events — warn-only.
_WARN_ONLY_CODES = {"SPL"}

# (kind_root, sign_source). sign_source = "amount" → suffix _in/_out from sign;
# "always_positive" → kind fixed; "always_negative" → kind fixed (fee).
_CASH_EVENT_CODES: dict[str, tuple[str, str]] = {
    "DIV":    ("dividend", "always_positive"),
    "DIVNRA": ("dividend", "always_positive"),
    "CDIV":   ("dividend", "always_positive"),
    "INT":    ("interest", "always_positive"),
    "GOLD":   ("fee",      "always_negative"),
    "MFEE":   ("fee",      "always_negative"),
    "MINT":   ("fee",      "always_negative"),
    "DTAX":   ("fee",      "always_negative"),
    "DFEE":   ("fee",      "always_negative"),
    "ACH":    ("transfer", "amount"),
    "ACATS":  ("transfer", "amount"),
}


def _to_cash_event(
    row: dict[str, str], account_display: str
) -> tuple[CashEvent | None, str | None]:
    """Try to convert a non-trade row to a CashEvent.

    Returns (event, warning):
      - (event, None) on a recognised cash-event row
      - (None, warning_text) on a recognised cash-event row that can't be emitted
        (zero amount, invalid date)

    Caller is responsible for routing rows whose Trans Code is in
    `_CASH_EVENT_CODES`; this helper assumes the code is a known cash event.
    """
    code = row.get("Trans Code", "").strip()
    kind_root, sign_source = _CASH_EVENT_CODES[code]
    amount = _money(row.get("Amount", ""))
    if amount == 0.0:
        return None, (
            f"Skipped {code!r} row with empty/zero Amount on "
            f"{row.get('Activity Date', '')!r}"
        )
    if sign_source == "amount":
        kind = f"{kind_root}_in" if amount > 0 else f"{kind_root}_out"
    else:
        kind = kind_root
    d = _parse_date(row.get("Activity Date", ""))
    if d is None:
        return None, (
            f"Skipped {code!r} row with invalid Activity Date "
            f"{row.get('Activity Date', '')!r}"
        )
    symbol = row.get("Instrument", "").strip() or None
    return (
        CashEvent(
            account=account_display,
            event_date=d,
            kind=kind,
            amount=abs(amount),
            ticker=symbol,
            description=row.get("Description", "").strip(),
        ),
        None,
    )


def _put_assignment_basis_offsets(rows: list[dict[str, str]]) -> dict[tuple[str, date], float]:
    """For each assigned short put, compute the premium that should reduce the
    basis of the assigned underlying purchase on the assignment date.

    Per IRS Pub 550, when a put you wrote is exercised against you, the
    premium received reduces the basis of the stock you receive. Robinhood
    records the assignment as `OASGN` and (Path A) also as a Buy of the
    underlying at the strike price, without applying the adjustment.

    Returns {(underlying_ticker, assignment_date) -> premium_offset}.
    Calls are out of scope for the v1 helper.
    """
    sto_qty: dict[str, float] = defaultdict(float)
    sto_amt: dict[str, float] = defaultdict(float)
    btc_amt: dict[str, float] = defaultdict(float)
    for row in rows:
        code = row.get("Trans Code", "").strip()
        if code not in {"STO", "BTC"}:
            continue
        symbol = row.get("Instrument", "").strip()
        opt = parse_option_symbol(symbol)
        if not opt or opt[1].call_put != "P":
            continue
        qty = abs(_qty(row.get("Quantity", "")))
        amount = abs(_money(row.get("Amount", "")))
        if code == "STO":
            sto_qty[symbol] += qty
            sto_amt[symbol] += amount
        else:
            btc_amt[symbol] += amount

    out: dict[tuple[str, date], float] = {}
    for row in rows:
        if row.get("Trans Code", "").strip() != "OASGN":
            continue
        symbol = row.get("Instrument", "").strip()
        opt = parse_option_symbol(symbol)
        if not opt or opt[1].call_put != "P":
            continue
        d = _parse_date(row.get("Activity Date", ""))
        if d is None:
            continue
        contract_qty = abs(_qty(row.get("Quantity", "")))
        if contract_qty <= 0 or sto_qty.get(symbol, 0) <= 0:
            continue
        per_contract = (sto_amt[symbol] - btc_amt.get(symbol, 0.0)) / sto_qty[symbol]
        if per_contract <= 0:
            continue
        key = (opt[0], d)
        out[key] = out.get(key, 0.0) + per_contract * contract_qty
    return out


class RobinhoodParser:
    name = "robinhood"
    REQUIRED_HEADERS = {"Activity Date", "Trans Code", "Instrument", "Quantity", "Amount"}

    def detect(self, headers: list[str]) -> bool:
        return self.REQUIRED_HEADERS.issubset(set(headers))

    def parse(self, rows: list[dict[str, str]], account_display: str) -> list[Trade]:
        basis_offsets = _put_assignment_basis_offsets(rows)
        trades: list[Trade] = []
        for i, row in enumerate(rows, start=1):
            code = row.get("Trans Code", "").strip()
            short_open = False
            short_close = False
            is_transfer = False
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
            elif code in _TRANSFER_CODES:
                action = None  # decided below from sign of quantity
                is_transfer = True
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

            if is_transfer:
                if qty == 0:
                    continue
                action = "Buy" if qty > 0 else "Sell"
                basis_source_xfer = "transfer_in" if qty > 0 else "transfer_out"
                qty = abs(qty)
                trades.append(Trade(
                    account=account_display,
                    date=trade_date,
                    ticker=ticker,
                    action=action,
                    quantity=qty,
                    proceeds=None,
                    cost_basis=None,
                    basis_unknown=True,
                    basis_source=basis_source_xfer,
                    option_details=opt[1] if opt else None,
                ))
                continue

            cost_basis = abs(amount) if action == "Buy" else None
            proceeds = abs(amount) if action == "Sell" else None

            if action == "Buy" and opt is None and cost_basis is not None:
                offset = basis_offsets.get((ticker, trade_date), 0.0)
                if offset > 0:
                    cost_basis = max(cost_basis - offset, 0.0)
                    basis_source_assignment = "put_assignment"
                else:
                    basis_source_assignment = None
            else:
                basis_source_assignment = None

            basis_source: str | None = None
            if short_open:
                basis_source = "option_short_open"
            elif short_close:
                basis_source = "option_short_close"
            elif basis_source_assignment is not None:
                basis_source = basis_source_assignment

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
        trades = self.parse(rows, account_display)
        cash_events: list[CashEvent] = []
        warnings: list[str] = []
        for row in rows:
            code = row.get("Trans Code", "").strip()
            if code in _TRADE_SIDE_CODES:
                continue
            if code in _WARN_ONLY_CODES:
                warnings.append(
                    f"Skipped {code!r} row on {row.get('Activity Date', '')!r} — "
                    f"corporate-action handled by splits subsystem"
                )
                continue
            if code in _CASH_EVENT_CODES:
                ev, warn = _to_cash_event(row, account_display)
                if ev is not None:
                    cash_events.append(ev)
                if warn is not None:
                    warnings.append(warn)
                continue
            # Unknown code — Task 12.
        return ImportResult(trades=trades, cash_events=cash_events, parse_warnings=warnings)
