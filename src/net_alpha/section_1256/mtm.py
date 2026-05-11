"""§1256 year-end mark-to-market — pure module (IRC §1256(a)(1)–(3))."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from net_alpha.models.domain import Lot, OptionDetails, Section1256MTM, Trade

_LT_FRACTION = Decimal("0.60")
_ST_FRACTION = Decimal("0.40")


@dataclass(frozen=True)
class OpenPosition:
    account: str
    ticker: str
    option_details: OptionDetails
    quantity: Decimal
    basis: Decimal


def position_key(*, account: str, ticker: str, option_details: OptionDetails) -> str:
    """Stable key: `{ticker}|{strike}|{expiry}|{cp}|{account}`."""
    o = option_details
    return f"{ticker}|{o.strike}|{o.expiry.isoformat()}|{o.call_put}|{account}"


def _is_eligible(trade: Trade, universe: set[str]) -> bool:
    return trade.option_details is not None and trade.ticker in universe


def open_section_1256_positions(
    trades: list[Trade],
    lots: list[Lot],
    universe: set[str],
    *,
    as_of: date,
) -> list[OpenPosition]:
    """Return one OpenPosition per still-open §1256 contract on `as_of`."""
    Key = tuple[str, str, float, str, str]
    net_qty: dict[Key, Decimal] = defaultdict(lambda: Decimal("0"))
    representative_opt: dict[Key, OptionDetails] = {}

    for t in trades:
        if not _is_eligible(t, universe):
            continue
        if t.date > as_of:
            continue
        o = t.option_details
        assert o is not None
        key: Key = (t.account, t.ticker, float(o.strike), o.expiry.isoformat(), o.call_put)
        delta = Decimal(str(t.quantity))
        if t.is_buy():
            net_qty[key] += delta
        else:
            net_qty[key] -= delta
        representative_opt.setdefault(key, o)

    positions: list[OpenPosition] = []
    for key, qty in net_qty.items():
        if qty == 0:
            continue
        account, ticker, strike, expiry_iso, cp = key
        opt = representative_opt[key]

        if qty > 0:
            matching = sorted(
                [lot for lot in lots if lot.ticker == ticker and lot.account == account and lot.option_details == opt],
                key=lambda lot: lot.date,
            )
            remaining = qty
            basis_total = Decimal("0")
            for lot in matching:
                if remaining <= 0:
                    break
                lot_qty = Decimal(str(lot.quantity))
                take = min(remaining, lot_qty)
                per_unit = Decimal(str(lot.adjusted_basis)) / lot_qty if lot_qty > 0 else Decimal("0")
                basis_total += take * per_unit
                remaining -= take
            positions.append(
                OpenPosition(account=account, ticker=ticker, option_details=opt, quantity=qty, basis=basis_total)
            )
        else:
            premium_received = Decimal("0")
            for t in trades:
                if t.date > as_of:
                    continue
                if not _is_eligible(t, universe):
                    continue
                if t.account != account or t.ticker != ticker or t.option_details != opt:
                    continue
                if t.is_sell() and t.proceeds is not None:
                    premium_received += Decimal(str(t.proceeds))
                elif t.is_buy() and t.cost_basis is not None:
                    premium_received -= Decimal(str(t.cost_basis))
            positions.append(
                OpenPosition(
                    account=account,
                    ticker=ticker,
                    option_details=opt,
                    quantity=qty,
                    basis=-premium_received,
                )
            )

    return positions


def _round_money(d: Decimal) -> Decimal:
    """Cents precision."""
    return d.quantize(Decimal("0.01"))


def mark_to_market(
    *,
    trades: list[Trade],
    lots: list[Lot],
    universe: set[str],
    tax_year: int,
    fmv_fn: Callable[[str, OptionDetails, int], tuple[Decimal | None, str]],
    prior_year_mtm_basis_fn: Callable[[str, int], Decimal | None],
) -> list[Section1256MTM]:
    """Emit Section1256MTM rows for each open §1256 position at year-end of `tax_year`."""
    from net_alpha.pricing.year_end import last_business_day as _lbd

    as_of = _lbd(tax_year)
    positions = open_section_1256_positions(trades, lots, universe, as_of=as_of)

    out: list[Section1256MTM] = []
    for pos in positions:
        pkey = position_key(account=pos.account, ticker=pos.ticker, option_details=pos.option_details)

        prior_mtm = prior_year_mtm_basis_fn(pkey, tax_year - 1)
        if prior_mtm is not None:
            basis_before = prior_mtm
        else:
            basis_before = pos.basis

        fmv, source = fmv_fn(pos.ticker, pos.option_details, tax_year)
        if fmv is None:
            fmv = Decimal("0")
            source = "missing"

        if pos.quantity > 0:
            unrealized = pos.quantity * fmv - basis_before
        else:
            unrealized = -basis_before - abs(pos.quantity) * fmv

        unrealized = _round_money(unrealized)
        lt = _round_money(unrealized * _LT_FRACTION)
        st = unrealized - lt

        out.append(
            Section1256MTM(
                position_key=pkey,
                tax_year=tax_year,
                last_business_day=as_of,
                fmv=fmv,
                basis_before=basis_before,
                unrealized_pnl=unrealized,
                long_term_portion=lt,
                short_term_portion=st,
                fmv_source=source,
                ticker=pos.ticker,
                account=pos.account,
            )
        )

    return out
