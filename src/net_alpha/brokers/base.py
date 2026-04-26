# src/net_alpha/brokers/base.py
from __future__ import annotations

from typing import Any, Protocol


class BrokerParser(Protocol):
    """A parser for one broker's CSV format. May produce Trades or RealizedGLLots."""

    name: str

    def detect(self, headers: list[str]) -> bool: ...
    def parse(self, rows: list[dict[str, str]], account_display: str) -> list[Any]: ...
