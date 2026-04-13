from __future__ import annotations

from net_alpha.db.repository import TradeRepository
from net_alpha.models.domain import Trade


def deduplicate_trades(
    trades: list[Trade],
    repo: TradeRepository,
) -> tuple[list[Trade], int]:
    """Filter out duplicate trades using two-signal strategy.

    Primary: raw_row_hash (SHA256 of entire raw CSV row).
    Secondary: semantic key (broker, date, ticker, action, quantity, proceeds).

    Returns (new_trades, skipped_count).
    """
    new_trades: list[Trade] = []
    skipped = 0

    for trade in trades:
        if _is_duplicate(trade, repo):
            skipped += 1
        else:
            new_trades.append(trade)

    return new_trades, skipped


def _is_duplicate(trade: Trade, repo: TradeRepository) -> bool:
    # Primary signal: raw_row_hash
    if trade.raw_row_hash is not None:
        if repo.find_by_hash(trade.raw_row_hash) is not None:
            return True

    # Secondary signal: semantic key
    existing = repo.find_by_semantic_key(
        account=trade.account,
        date_str=trade.date.isoformat(),
        ticker=trade.ticker,
        action=trade.action,
        quantity=trade.quantity,
        proceeds=trade.proceeds,
    )
    return existing is not None
