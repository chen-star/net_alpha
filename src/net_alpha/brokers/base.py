# src/net_alpha/brokers/base.py
from __future__ import annotations

from typing import Protocol

from net_alpha.models.domain import Trade


class BrokerParser(Protocol):
    name: str

    def detect(self, headers: list[str]) -> bool: ...
    def parse(self, rows: list[dict[str, str]], account_display: str) -> list[Trade]: ...
