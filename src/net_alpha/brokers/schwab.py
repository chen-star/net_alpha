# src/net_alpha/brokers/schwab.py
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime

from net_alpha.ingest.option_parser import parse_option_symbol
from net_alpha.models.domain import CashEvent, ImportResult, Trade

# Schwab buy actions (v1 KNOWN_BROKER_SCHEMAS: "Buy", "Reinvest"; also options: "Buy to Open")
_BUY_ACTIONS = {"Buy", "Reinvest Shares", "Reinvest", "Buy to Open"}
# Schwab sell actions (v1: "Sell"; also options: "Sell to Close")
_SELL_ACTIONS = {"Sell", "Sell to Close"}
# Short-option lifecycle actions. A "Sell to Open" opens a short option position
# (you receive premium); a "Buy to Close" closes one (you pay to terminate the
# obligation). v1 dropped these silently to keep the wash-sale engine simple,
# but the portfolio view needs them so the user sees premium income, open short
# positions, and round-trip cash flow on tickers like UUUU/HIMS.
_SHORT_OPTION_OPEN_ACTIONS = {"Sell to Open"}
_SHORT_OPTION_CLOSE_ACTIONS = {"Buy to Close"}
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
    "Wire Received": ("transfer", "amount"),
    "Wire Sent": ("transfer", "amount"),
    "Journal": ("transfer", "amount"),
    "Futures MM Sweep": ("sweep", "amount"),
    "Qualified Dividend": ("dividend", "always_positive"),
    "Non-Qualified Div": ("dividend", "always_positive"),
    "Pr Yr Non-Qual Div": ("dividend", "always_positive"),
    "Cash Dividend": ("dividend", "always_positive"),
    "Cash In Lieu": ("dividend", "always_positive"),
    "Reinvest Dividend": ("dividend", "always_positive"),
    "Long Term Cap Gain": ("dividend", "always_positive"),
    "Short Term Cap Gain": ("dividend", "always_positive"),
    "Credit Interest": ("interest", "always_positive"),
    "Bank Interest": ("interest", "always_positive"),
    "Margin Interest": ("fee", "always_negative"),
    "ADR Mgmt Fee": ("fee", "always_negative"),
    "Foreign Tax Paid": ("fee", "always_negative"),
    "Service Fee": ("fee", "always_negative"),
}

# Non-trade actions handled by trade-side logic — never emitted as cash events.
# `Assigned` and `Expired` are option-lifecycle markers consumed by the trade
# branch (basis offsets / silent close); `Reverse Split` is logged by Schwab
# but the actual share-quantity adjustment comes from the splits subsystem.
_TRADE_SIDE_NON_TRADE_ACTIONS = {
    "Reverse Split",
    "Assigned",
    "Expired",
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


def _assigned_put_symbols(rows: list[dict[str, str]]) -> set[str]:
    """Raw option symbols of puts that have at least one Assigned row.

    These chains are consumed by `_put_assignment_basis_offsets` to fold the
    premium into the underlying-stock cost basis. Emitting STO/BTC trades for
    the same symbols would double-count the premium (once as Sell proceeds,
    once as basis reduction). Calls are not basis-adjusted by the helper, so
    sold-call assignments still emit normally — premium becomes a Sell trade.
    """
    out: set[str] = set()
    for row in rows:
        if row.get("Action", "").strip() != "Assigned":
            continue
        symbol = row.get("Symbol", "").strip()
        opt = parse_option_symbol(symbol)
        if opt is not None and opt[1].call_put == "P":
            out.add(symbol)
    return out


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
) -> tuple[object | None, str | None]:
    """Try to convert a non-trade row to a CashEvent.

    Returns (event, warning):
      - (event, None) on a recognised cash-event row
      - (None, None) if the row is a known non-cash-event action (e.g. Security Transfer)
      - (None, warning_text) on an unknown non-trade action
    """
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
        assigned_puts = _assigned_put_symbols(rows)
        # Map (symbol → assignment_date) so we can pair the assigned-put STO
        # with a synthetic close on the right date for the option counter.
        assignment_dates: dict[str, date] = {}
        for row in rows:
            if row.get("Action", "").strip() != "Assigned":
                continue
            sym = row.get("Symbol", "").strip()
            d = _parse_date(row.get("Date", ""))
            if sym in assigned_puts and d is not None and sym not in assignment_dates:
                assignment_dates[sym] = d
        for i, row in enumerate(rows, start=1):
            action_raw = row["Action"].strip()

            is_transfer = action_raw in _TRANSFER_ACTIONS
            short_open = False
            short_close = False
            short_open_assigned = False
            if action_raw in _BUY_ACTIONS:
                action = "Buy"
            elif action_raw in _SELL_ACTIONS:
                action = "Sell"
            elif action_raw in _SHORT_OPTION_OPEN_ACTIONS:
                action = "Sell"
                short_open = True
                # An STO whose put eventually gets assigned must NOT be hidden
                # — the user expects to see the premium event in the timeline.
                # We mark it with a distinct basis_source so positions.py
                # excludes it from realized-P/L aggregation (the premium is
                # already captured via the underlying-stock basis offset, so
                # counting it again here would double-count). Cash-flow uses
                # gross_cash_impact, which still records the real premium
                # credit — so emitting fixes the previously-missing inflow.
                short_open_assigned = row["Symbol"].strip() in assigned_puts
            elif action_raw in _SHORT_OPTION_CLOSE_ACTIONS:
                # A real BTC of an assigned-put symbol shouldn't happen (the
                # position closed via assignment, not market) — but if Schwab
                # logs one, suppress it: the basis-offset helper has already
                # consumed those amounts.
                if row["Symbol"].strip() in assigned_puts:
                    continue
                action = "Buy"
                short_close = True
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
            if short_open_assigned:
                # Distinct marker so realized-P/L aggregation skips it (premium
                # already folded into the underlying-stock basis); cash-flow
                # still picks up the gross_cash_impact credit.
                basis_source = "option_short_open_assigned"
            elif short_open:
                # STO: the "Sell" carries the premium received as proceeds.
                # Marker lets the holdings/lots layer recognise short positions.
                basis_source = "option_short_open"
            elif short_close:
                # BTC: the "Buy" carries the close cost as cost_basis. The
                # marker lets the wash-sale engine skip lot creation — a BTC
                # closes a short, it doesn't open a new long lot.
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
                "gross_cash_impact": amount,  # signed; from CSV `Amount`
            }
            if basis_source is not None:
                kwargs["basis_source"] = basis_source
            trades.append(Trade(**kwargs))

        # For every assigned-put STO we just emitted, append a synthetic
        # closing trade ($0 cost, gross_cash_impact=0) on the assignment
        # date. This lets the open-option counter / lots-view see the
        # short put as closed even though it never had a real BTC.
        for t in list(trades):
            if t.basis_source != "option_short_open_assigned":
                continue
            opt = t.option_details
            if opt is None:
                continue
            sym_raw = f"{t.ticker} {opt.expiry.strftime('%m/%d/%Y')} {opt.strike:.2f} {opt.call_put}"
            close_date = assignment_dates.get(sym_raw, t.date)
            trades.append(
                Trade(
                    account=t.account,
                    date=close_date,
                    ticker=t.ticker,
                    action="Buy",
                    quantity=t.quantity,
                    proceeds=None,
                    cost_basis=0.0,
                    basis_source="option_short_close_assigned",
                    gross_cash_impact=0.0,
                    option_details=opt,
                )
            )

        # Assign within-batch occurrence indices to trades whose canonical
        # fields are byte-for-byte identical (Schwab can split a fill across
        # two same-day same-price rows). Without this they collapse to the
        # same natural key and the dedup pre-filter drops one as a "duplicate"
        # (we have seen the user's GPRO 07/29 100sh sell get dropped this way).
        seen: dict[str, int] = {}
        for t in trades:
            base = t.compute_natural_key()  # uses occurrence_index=0 → legacy formula
            seen[base] = seen.get(base, -1) + 1
            if seen[base] > 0:
                t.occurrence_index = seen[base]
        return trades

    def parse_full(self, rows: list[dict[str, str]], account_display: str) -> ImportResult:
        trades = self.parse(rows, account_display)
        cash_events: list = []
        warnings: list[str] = []
        # Set of action strings handled by the trade-side branch, OR as cash events;
        # anything else is unknown.
        known_trade_actions = (
            _BUY_ACTIONS
            | _SELL_ACTIONS
            | _TRANSFER_ACTIONS
            | _TRADE_SIDE_NON_TRADE_ACTIONS
            | _SHORT_OPTION_OPEN_ACTIONS
            | _SHORT_OPTION_CLOSE_ACTIONS
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
                warnings.append(f"Unknown action {action!r} on {row.get('Date', '')!r} (row skipped)")
        return ImportResult(trades=trades, cash_events=cash_events, parse_warnings=warnings)
