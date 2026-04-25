# src/net_alpha/brokers/registry.py
from __future__ import annotations

from net_alpha.brokers.base import BrokerParser
from net_alpha.brokers.schwab import SchwabParser

PARSERS: list[BrokerParser] = [SchwabParser()]


def detect_broker(headers: list[str]) -> BrokerParser | None:
    for p in PARSERS:
        if p.detect(headers):
            return p
    return None
