# src/net_alpha/brokers/schwab.py
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime

from net_alpha.ingest.option_parser import parse_option_symbol
from net_alpha.models.domain import Trade

# Schwab buy actions (v1 KNOWN_BROKER_SCHEMAS: "Buy", "Reinvest"; also options: "Buy to Open")
_BUY_ACTIONS = {"Buy", "Reinvest Shares", "Reinvest", "Buy to Open"}
# Schwab sell actions (v1: "Sell"; also options: "Sell to Close")
_SELL_ACTIONS = {"Sell", "Sell to Close"}
# Account transfers: signed quantity (+ in / − out). Not real trades, but they
# move shares in/out of an account, so they must adjust open lots. Mapped to
# Buy/Sell with basis_source="transfer_in"/"transfer_out" so downstream code
# (wash-sale engine, calendar P&L, equity curve) can ignore them while the
# position calculator treats them as quantity-only adjustments.
_TRANSFER_ACTIONS = {"Security Transfer", "Journaled Shares"}

# Cash-event action mappings (kind, sign-source).
# sign_source = "amount" → kind suffix (_in/_out) chosen by the sign of CSV Amount.
# sign_source = "always_positive" → kind is fixed; amount stored as |Amount|.
# sign_source = "always_negative" → kind is fixed (fee); amount stored as |Amount|.
_CASH_EVENT_ACTIONS: dict[str, tuple[str, str]] = {
    "MoneyLink Transfer": ("transfer", "amount"),
    "Wire Received":      ("transfer", "amount"),
    "Wire Sent":          ("transfer", "amount"),
    "Journal":            ("transfer", "amount"),
    "Futures MM Sweep":   ("sweep",    "amount"),
    "Qualified Dividend":   ("dividend", "always_positive"),
    "Non-Qualified Div":    ("dividend", "always_positive"),
    "Pr Yr Non-Qual Div":   ("dividend", "always_positive"),
    "Cash Dividend":        ("dividend", "always_positive"),
    "Cash In Lieu":         ("dividend", "always_positive"),
    "Credit Interest":      ("interest", "always_positive"),
    "Bank Interest":        ("interest", "always_positive"),
    "Margin Interest":      ("fee", "always_negative"),
    "ADR Mgmt Fee":         ("fee", "always_negative"),
    "Foreign Tax Paid":     ("fee", "always_negative"),
    "Service Fee":          ("fee", "always_negative"),
}

# Non-trade actions handled by trade-side logic (existing) — never cash events.
_TRADE_SIDE_NON_TRADE_ACTIONS = {
    "Reverse Split", "Assigned", "Expired",
}


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


def _put_assignment_basis_offsets(rows: list[dict[str, str]]) -> dict[tuple[str, date], float]:
    """For each assigned short put, compute the premium that should reduce the
    basis of the assigned underlying purchase on the assignment date.

    Per IRS Pub 550, when a put you wrote is exercised against you, the premium
    received reduces the basis of the stock you receive. Schwab's Transactions
    CSV records the assignment as a `Buy` of the underlying at the strike price
    *without* applying this adjustment, so we have to do it here.

    Returns a map {(underlying_ticker, assignment_date) → premium_offset}.
    Premium is computed per-contract as (sum Sell-to-Open amounts − sum
    Buy-to-Close amounts) / sum Sell-to-Open quantity, multiplied by the
    Assigned quantity. Calls are out of scope for this v1 helper.
    """
    sto_qty: dict[str, float] = defaultdict(float)
    sto_amt: dict[str, float] = defaultdict(float)
    btc_amt: dict[str, float] = defaultdict(float)
    for row in rows:
        action = row.get("Action", "").strip()
        if action not in {"Sell to Open", "Buy to Close"}:
            continue
        symbol = row.get("Symbol", "").strip()
        opt = parse_option_symbol(symbol)
        if not opt or opt[1].call_put != "P":
            continue
        qty = abs(_qty(row.get("Quantity", "")))
        amount = abs(_money(row.get("Amount", "")))
        if action == "Sell to Open":
            sto_qty[symbol] += qty
            sto_amt[symbol] += amount
        else:
            btc_amt[symbol] += amount

    out: dict[tuple[str, date], float] = {}
    for row in rows:
        if row.get("Action", "").strip() != "Assigned":
            continue
        symbol = row.get("Symbol", "").strip()
        opt = parse_option_symbol(symbol)
        if not opt or opt[1].call_put != "P":
            continue
        d = _parse_date(row.get("Date", ""))
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


def _to_cash_event(
    row: dict[str, str],
    account_display: str,
) -> "tuple[object | None, str | None]":
    """Try to convert a non-trade row to a CashEvent.

    Returns (event, warning):
      - (event, None) on a recognised cash-event row
      - (None, None) if the row is a known non-cash-event action (e.g. Security Transfer)
      - (None, warning_text) on an unknown non-trade action
    """
    from net_alpha.models.domain import CashEvent

    action = row.get("Action", "").strip()
    if action in _CASH_EVENT_ACTIONS:
        kind_root, sign_source = _CASH_EVENT_ACTIONS[action]
        amount_raw = row.get("Amount", "")
        amount = _money(amount_raw)
        if amount == 0.0:
            return None, f"Skipped {action!r} row with empty/zero Amount on {row.get('Date', '')!r}"

        if sign_source == "amount":
            kind = f"{kind_root}_in" if amount > 0 else f"{kind_root}_out"
        elif sign_source == "always_positive":
            kind = kind_root
        else:  # always_negative — fee
            kind = kind_root
        d = _parse_date(row.get("Date", ""))
        if d is None:
            return None, f"Skipped {action!r} row with invalid Date {row.get('Date', '')!r}"
        symbol = row.get("Symbol", "").strip() or None
        # Underlying ticker for option dividend rows is rare; treat Symbol as ticker as-is.
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
    return None, None


class SchwabParser:
    name = "schwab"
    REQUIRED_HEADERS = {"Date", "Action", "Symbol", "Quantity", "Amount"}

    def detect(self, headers: list[str]) -> bool:
        return self.REQUIRED_HEADERS.issubset(set(headers))

    def parse(self, rows: list[dict[str, str]], account_display: str) -> list[Trade]:
        trades: list[Trade] = []
        basis_offsets = _put_assignment_basis_offsets(rows)
        for i, row in enumerate(rows, start=1):
            action_raw = row["Action"].strip()

            is_transfer = action_raw in _TRANSFER_ACTIONS
            if action_raw in _BUY_ACTIONS:
                action = "Buy"
            elif action_raw in _SELL_ACTIONS:
                action = "Sell"
            elif is_transfer:
                action = None  # decided below from sign of quantity
            else:
                # Non-trade rows (Cash Dividend, Journal, Wire Transferred, etc.) — skip
                continue

            try:
                trade_date = datetime.strptime(row["Date"].strip()[:10], "%m/%d/%Y").date()
            except ValueError as e:
                raise ValueError(f"Row {i}: 'Date' value {row['Date']!r} is not a valid date") from e

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

            if is_transfer:
                if qty == 0:
                    continue
                action = "Buy" if qty > 0 else "Sell"
                basis_source = "transfer_in" if qty > 0 else "transfer_out"
                qty = abs(qty)
                # Schwab includes a Price column (per share) on Journaled Shares
                # but never on Security Transfer. Use it as a rough basis estimate
                # for transfer-in lots when present; otherwise leave unknown.
                price_raw = row.get("Price", "").replace("$", "").replace(",", "").strip()
                price_val: float | None = None
                if price_raw:
                    try:
                        price_val = float(price_raw)
                    except ValueError:
                        price_val = None
                cost_basis = (price_val * qty) if (action == "Buy" and price_val) else None
                proceeds = None
                trades.append(
                    Trade(
                        account=account_display,
                        date=trade_date,
                        ticker=ticker,
                        action=action,
                        quantity=qty,
                        proceeds=proceeds,
                        cost_basis=cost_basis,
                        basis_unknown=True,
                        basis_source=basis_source,
                        option_details=opt[1] if opt else None,
                    )
                )
                continue

            cost_basis = abs(amount) if action == "Buy" else None
            proceeds = abs(amount) if action == "Sell" else None

            # Optional "Cost Basis" column — present in some Schwab exports.
            # Use it to populate cost_basis on sell trades so the engine can
            # detect losses without needing a prior matching buy in the DB.
            if action == "Sell" and "Cost Basis" in row:
                cb_raw = row["Cost Basis"].replace("$", "").replace(",", "").strip()
                if cb_raw:
                    try:
                        cost_basis = abs(float(cb_raw))
                    except ValueError:
                        pass

            basis_source: str | None = None
            if action == "Buy" and opt is None and cost_basis is not None:
                offset = basis_offsets.get((ticker, trade_date), 0.0)
                if offset > 0:
                    cost_basis = max(cost_basis - offset, 0.0)
                    basis_source = "put_assignment"

            kwargs: dict[str, object] = {
                "account": account_display,
                "date": trade_date,
                "ticker": ticker,
                "action": action,
                "quantity": qty,
                "proceeds": proceeds,
                "cost_basis": cost_basis,
                "option_details": opt[1] if opt else None,
                "gross_cash_impact": amount,  # signed; from CSV `Amount`
            }
            if basis_source is not None:
                kwargs["basis_source"] = basis_source
            trades.append(Trade(**kwargs))
        return trades

    def parse_full(self, rows: list[dict[str, str]], account_display: str) -> "ImportResult":
        from net_alpha.models.domain import ImportResult

        trades = self.parse(rows, account_display)
        cash_events: list = []
        warnings: list[str] = []
        # Set of action strings handled by the trade-side branch, OR as cash events;
        # anything else is unknown.
        known_trade_actions = (
            _BUY_ACTIONS | _SELL_ACTIONS | _TRANSFER_ACTIONS | _TRADE_SIDE_NON_TRADE_ACTIONS
        )
        for row in rows:
            action = row.get("Action", "").strip()
            if action in known_trade_actions:
                continue
            if action in _CASH_EVENT_ACTIONS:
                ev, warn = _to_cash_event(row, account_display)
                if ev is not None:
                    cash_events.append(ev)
                if warn is not None:
                    warnings.append(warn)
            else:
                # Unknown non-trade action — warn but don't crash.
                warnings.append(
                    f"Unknown action {action!r} on {row.get('Date', '')!r} (row skipped)"
                )
        return ImportResult(trades=trades, cash_events=cash_events, parse_warnings=warnings)
