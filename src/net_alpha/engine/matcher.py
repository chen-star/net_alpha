from __future__ import annotations

from datetime import date

from net_alpha.models.domain import Trade


def is_within_wash_sale_window(sale_date: date, other_date: date) -> bool:
    """Check if other_date falls within the 30-day wash sale window of sale_date.

    The window spans 30 calendar days before through 30 calendar days after the sale.
    """
    delta = (other_date - sale_date).days
    return -30 <= delta <= 30


def get_match_confidence(
    loss_sale: Trade,
    candidate: Trade,
    etf_pairs: dict[str, list[str]],
) -> str | None:
    """Determine if candidate could trigger a wash sale for loss_sale.

    Returns a confidence label ("Confirmed", "Probable", "Unclear") or None.
    """
    # Special case: selling a put on same underlying as a stock loss
    if (
        candidate.is_sell()
        and candidate.is_option()
        and candidate.option_details.call_put == "P"
        and not loss_sale.is_option()
        and loss_sale.ticker == candidate.ticker
    ):
        return "Unclear"

    # All other triggers must be buys
    if not candidate.is_buy():
        return None

    # Same ticker
    if loss_sale.ticker == candidate.ticker:
        # Both equities
        if not loss_sale.is_option() and not candidate.is_option():
            return "Confirmed"

        # Loss sale is equity, candidate is option
        if not loss_sale.is_option() and candidate.is_option():
            if candidate.option_details.call_put == "C":
                return "Probable"
            return None

        # Loss sale is option, candidate is equity
        if loss_sale.is_option() and not candidate.is_option():
            return "Probable"

        # Both options on same underlying
        if loss_sale.is_option() and candidate.is_option():
            if (
                loss_sale.option_details.strike == candidate.option_details.strike
                and loss_sale.option_details.expiry == candidate.option_details.expiry
                and loss_sale.option_details.call_put == candidate.option_details.call_put
            ):
                return "Confirmed"
            return "Probable"

    # ETF substantially-identical pairs
    if _are_substantially_identical(loss_sale.ticker, candidate.ticker, etf_pairs):
        return "Unclear"

    return None


def _are_substantially_identical(ticker_a: str, ticker_b: str, etf_pairs: dict[str, list[str]]) -> bool:
    """Check if two different tickers belong to the same ETF group."""
    if ticker_a == ticker_b:
        return False
    for group in etf_pairs.values():
        if ticker_a in group and ticker_b in group:
            return True
    return False
