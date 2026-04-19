from datetime import date

from net_alpha.engine.detector import detect_wash_sales
from net_alpha.models.domain import DetectionResult, Trade


def simulate_trade(
    existing_trades: list[Trade],
    etf_pairs: dict[str, list[str]],
    action: str,
    ticker: str,
    quantity: float,
    price: float,
    trade_date: date,
) -> tuple[bool, DetectionResult | None, str | None, str | None]:
    """
    Simulates a trade and returns (success, result, error_msg, virtual_id).
    success is False if inputs are invalid.
    """
    try:
        # Create virtual trade
        virtual_trade = Trade(
            account="SIMULATION",
            date=trade_date,
            ticker=ticker.upper(),
            action=action.capitalize(),
            quantity=quantity,
            proceeds=quantity * price if action.lower() == "sell" else None,
            cost_basis=(quantity * price) + 100.0 if action.lower() == "sell" else None,  # Simulate a loss for sells
        )

        combined_trades = existing_trades + [virtual_trade]
        result = detect_wash_sales(combined_trades, etf_pairs)
        return True, result, None, virtual_trade.id
    except Exception as e:
        return False, None, str(e), None
