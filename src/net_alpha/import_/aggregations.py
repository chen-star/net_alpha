"""Pure aggregator for import metadata shown on the Imports page detail panel.

Inputs are the parsed Trade list for a single import plus any parse warnings
captured by the broker parser. Output is persisted to the imports table by
the caller (the upload route) and read back by list_imports / detail.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date

from net_alpha.models.domain import Trade


@dataclass(frozen=True)
class ImportAggregates:
    min_trade_date: date | None
    max_trade_date: date | None
    equity_count: int
    option_count: int
    option_expiry_count: int  # currently always 0 — Schwab parser drops "Expired" rows;
    # column reserved for when raw broker actions are preserved.
    parse_warnings: list[str] = field(default_factory=list)


def compute_import_aggregates(
    *,
    trades: Iterable[Trade],
    parse_warnings: Iterable[str],
) -> ImportAggregates:
    trades_list = list(trades)
    if not trades_list:
        return ImportAggregates(
            min_trade_date=None,
            max_trade_date=None,
            equity_count=0,
            option_count=0,
            option_expiry_count=0,
            parse_warnings=list(parse_warnings),
        )
    dates = [t.date for t in trades_list]
    equity = sum(1 for t in trades_list if t.option_details is None)
    option = sum(1 for t in trades_list if t.option_details is not None)
    return ImportAggregates(
        min_trade_date=min(dates),
        max_trade_date=max(dates),
        equity_count=equity,
        option_count=option,
        option_expiry_count=0,
        parse_warnings=list(parse_warnings),
    )
