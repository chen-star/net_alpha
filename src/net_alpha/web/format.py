"""Pure presentation helpers for web templates."""

from __future__ import annotations

from net_alpha.models.domain import OptionDetails, Trade


def _format_option_suffix(opt: OptionDetails) -> str:
    """e.g. 'CALL $400 06/18/26' — compact, dense, sortable-readable."""
    cp = "CALL" if opt.call_put == "C" else "PUT"
    strike = f"${opt.strike:g}"
    expiry = opt.expiry.strftime("%m/%d/%y")
    return f"{cp} {strike} {expiry}"


def display_action(t: Trade, *, assigned_from: OptionDetails | None = None) -> str:
    """User-facing action label.

    Transfers are stored as Buy/Sell with basis_source set to transfer_in /
    transfer_out so engine logic treats them uniformly. The Timeline column
    re-expands the label for clarity. Option trades are extended with the
    contract details (CALL/PUT, strike, expiry) so the user can tell at a
    glance whether a row is stock or an option position.

    ``assigned_from`` lets the timeline surface the originating short option
    on a put-assignment Buy row, so the user sees "Buy 100 (assigned from
    PUT $7 02/20/26)" without a separate synthetic close-by-assignment row.
    """
    if t.basis_source == "transfer_in":
        return "Transfer In"
    if t.basis_source == "transfer_out":
        return "Transfer Out"
    if t.basis_source == "put_assignment" and assigned_from is not None:
        return f"Buy (assigned from {_format_option_suffix(assigned_from)})"
    if t.basis_source == "option_short_open_assigned" and t.option_details is not None:
        return f"Sell to Open {_format_option_suffix(t.option_details)} (assigned)"
    if t.basis_source == "option_short_close_assigned" and t.option_details is not None:
        return f"Closed by Assignment {_format_option_suffix(t.option_details)}"
    if t.basis_source == "option_short_close_expiry" and t.option_details is not None:
        return f"Closed by Expiry {_format_option_suffix(t.option_details)}"
    if t.option_details is not None:
        if t.basis_source == "option_short_open":
            return f"Sell to Open {_format_option_suffix(t.option_details)}"
        if t.basis_source == "option_short_close":
            return f"Buy to Close {_format_option_suffix(t.option_details)}"
        return f"{t.action} {_format_option_suffix(t.option_details)}"
    return t.action


from decimal import ROUND_HALF_EVEN, Decimal


def fmt_quantity(value: Decimal | float | int | None) -> str:
    """Render a share-quantity-like number.

    Whole values render as integers (``11`` not ``11.0000``). Fractional
    values render with up to four decimal places, banker's-rounded, with
    trailing zeros stripped (``1.5`` not ``1.5000``). ``None`` renders as
    an em dash.
    """
    if value is None:
        return "—"
    d = value if isinstance(value, Decimal) else Decimal(str(value))
    quantized = d.quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN)
    if quantized == quantized.to_integral_value():
        return str(int(quantized))
    text = format(quantized, "f").rstrip("0").rstrip(".")
    return text


from typing import Literal

Density = Literal["compact", "comfortable", "tax-view"]


def fmt_currency(
    amount: Decimal | float | int | None,
    *,
    density: str = "comfortable",
) -> str:
    """Render a USD amount.

    Default 2dp. In ``compact`` density, amounts whose absolute value is
    ≥ $10,000 round to whole dollars. ``tax-view`` follows ``comfortable``
    (always 2dp). Unknown density values fall back to ``comfortable``
    rather than raising — formatters must never block render.
    """
    if amount is None:
        return "—"
    d = amount if isinstance(amount, Decimal) else Decimal(str(amount))
    use_zero_dp = density == "compact" and abs(d) >= Decimal("10000")
    if use_zero_dp:
        rounded = d.quantize(Decimal("1"), rounding=ROUND_HALF_EVEN)
        body = f"{abs(rounded):,}"
    else:
        rounded = d.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
        body = f"{abs(rounded):,.2f}"
    sign = "-" if d < 0 else ""
    return f"{sign}${body}"


def fmt_percent(value: Decimal | float | int | None) -> str:
    """Render a fractional value as a percent with one decimal place.

    Input is fractional (``0.354`` → ``"35.4%"``), not basis-points or
    pre-multiplied. ``None`` renders as an em dash.
    """
    if value is None:
        return "—"
    d = value if isinstance(value, Decimal) else Decimal(str(value))
    pct = (d * Decimal("100")).quantize(Decimal("0.1"), rounding=ROUND_HALF_EVEN)
    return f"{pct:.1f}%"
