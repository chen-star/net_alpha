# src/net_alpha/brokers/schwab.py
from __future__ import annotations

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


def _scan_assignment_cycles(
    rows: list[dict[str, str]],
) -> tuple[dict[tuple[str, date], float], dict[int, date], set[int]]:
    """Walk rows in CSV order and bucket STO/BTC events into assignment cycles.

    A cycle is the sequence of STO/BTC events for one option (keyed by
    ``(ticker, strike, expiry, call_put)``) that ends either when an
    ``Assigned`` row appears OR when BTC fully closes the open contracts
    (so a closed-then-reopened position doesn't leak premia into the next
    cycle's assignment offset).

    Returns three structures:

    * ``basis_offsets`` — ``{(underlying_ticker, assignment_date) → premium}``
      consumed by the main parse loop to reduce the underlying-stock Buy's
      cost basis (IRS Pub 550). Aggregated across multiple cycles on the
      same day at the same ticker.
    * ``sto_close_dates`` — ``{row_index → assignment_date}`` for STO rows
      whose cycle ended with assignment. The main loop emits a synthetic
      ``option_short_close_assigned`` trade on this date alongside the STO.
    * ``suppress_btc_indices`` — row indices of BTC rows whose cycle ended
      with assignment; their premium was already folded into the offset, so
      the main loop must NOT also emit them as regular BTC trades.

    Calls are out of scope — only puts produce basis offsets.
    """

    def _fresh() -> dict[str, object]:
        return {
            "sto_qty": 0.0,
            "sto_amt": 0.0,
            "btc_qty": 0.0,
            "btc_amt": 0.0,
            "sto_idx": [],
            "btc_idx": [],
        }

    cycles: dict[tuple, dict[str, object]] = {}
    basis_offsets: dict[tuple[str, date], float] = {}
    sto_close_dates: dict[int, date] = {}
    suppress_btc_indices: set[int] = set()

    for i, row in enumerate(rows):
        action = row.get("Action", "").strip()
        symbol = row.get("Symbol", "").strip()
        opt = parse_option_symbol(symbol)
        if not opt or opt[1].call_put != "P":
            continue
        key = (opt[0], float(opt[1].strike), opt[1].expiry.isoformat(), opt[1].call_put)
        c = cycles.setdefault(key, _fresh())

        if action == "Sell to Open":
            c["sto_qty"] += abs(_qty(row.get("Quantity", "")))  # type: ignore[operator]
            c["sto_amt"] += abs(_money(row.get("Amount", "")))  # type: ignore[operator]
            c["sto_idx"].append(i)  # type: ignore[attr-defined]
        elif action == "Buy to Close":
            c["btc_qty"] += abs(_qty(row.get("Quantity", "")))  # type: ignore[operator]
            c["btc_amt"] += abs(_money(row.get("Amount", "")))  # type: ignore[operator]
            c["btc_idx"].append(i)  # type: ignore[attr-defined]
            # Position fully closed by BTC → cycle ends without assignment.
            # Future STOs of the same option start a fresh cycle so their
            # premia aren't entangled with this closed cycle's events.
            if c["sto_qty"] - c["btc_qty"] <= 1e-6:  # type: ignore[operator]
                cycles[key] = _fresh()
        elif action == "Assigned":
            d = _parse_date(row.get("Date", ""))
            if d is None:
                continue
            contract_qty = abs(_qty(row.get("Quantity", "")))
            sto_qty_total: float = c["sto_qty"]  # type: ignore[assignment]
            if contract_qty > 0 and sto_qty_total > 0:
                per_contract = (c["sto_amt"] - c["btc_amt"]) / sto_qty_total  # type: ignore[operator]
                if per_contract > 0:
                    okey = (opt[0], d)
                    basis_offsets[okey] = basis_offsets.get(okey, 0.0) + per_contract * contract_qty
                for sto_i in c["sto_idx"]:  # type: ignore[attr-defined]
                    sto_close_dates[sto_i] = d
                for btc_i in c["btc_idx"]:  # type: ignore[attr-defined]
                    suppress_btc_indices.add(btc_i)
            cycles[key] = _fresh()

    return basis_offsets, sto_close_dates, suppress_btc_indices


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
        basis_offsets, sto_close_dates, suppress_btc_indices = _scan_assignment_cycles(rows)
        for i, row in enumerate(rows):
            row_num = i + 1  # 1-based for human-facing error messages
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
                # counting it again here would double-count). Cycle-aware:
                # only STOs whose cycle ENDED with an Assigned row are marked,
                # not every STO that shares the option symbol with one.
                short_open_assigned = i in sto_close_dates
            elif action_raw in _SHORT_OPTION_CLOSE_ACTIONS:
                # BTCs whose cycle ended with an Assignment are folded into the
                # basis offset and must NOT also emit as regular BTCs (double-
                # counting). BTCs that genuinely closed a non-assignment cycle
                # are emitted normally.
                if i in suppress_btc_indices:
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
                raise ValueError(f"Row {row_num}: 'Date' value {row['Date']!r} is not a valid date") from e

            symbol = row["Symbol"].strip()
            opt = parse_option_symbol(symbol)
            ticker = opt[0] if opt else symbol

            qty_raw = row["Quantity"].replace(",", "").strip()
            amount_raw = row["Amount"].replace("$", "").replace(",", "").strip()

            try:
                qty = float(qty_raw) if qty_raw else 0.0
            except ValueError as e:
                raise ValueError(f"Row {row_num}: 'Quantity' value {row['Quantity']!r} is not numeric") from e

            try:
                amount = float(amount_raw) if amount_raw else 0.0
            except ValueError as e:
                raise ValueError(f"Row {row_num}: 'Amount' value {row['Amount']!r} is not numeric") from e

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
                # Preserve the broker statement date on transfer-IN rows so
                # it stays available when the user later overrides
                # ``Trade.date`` with the original acquisition date via the
                # set-basis editor (§1223(3) holding-period correction).
                xfer_date = trade_date if action == "Buy" else None
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
                        transfer_date=xfer_date,
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

            # Inline synthetic close for an assigned-put STO: emit the
            # ``option_short_close_assigned`` trade on the actual Assigned-row
            # date recorded in ``sto_close_dates`` during the row scan. The
            # close date is structurally derived from the cycle scan, so it
            # tolerates any strike formatting Schwab uses in the symbol.
            if short_open_assigned and opt is not None:
                close_date = sto_close_dates.get(i, trade_date)
                trades.append(
                    Trade(
                        account=account_display,
                        date=close_date,
                        ticker=ticker,
                        action="Buy",
                        quantity=qty,
                        proceeds=None,
                        cost_basis=0.0,
                        basis_source="option_short_close_assigned",
                        gross_cash_impact=0.0,
                        option_details=opt[1],
                    )
                )

        # Synthetic close trades for assigned-put STOs are emitted inline in
        # the main loop above (see the `if short_open_assigned` block right
        # after the STO Trade append). No post-loop reconstruction needed.

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
