# src/net_alpha/brokers/registry.py
from __future__ import annotations

from net_alpha.brokers.base import BrokerParser
from net_alpha.brokers.schwab import SchwabParser
from net_alpha.brokers.schwab_realized_gl import SchwabRealizedGLParser

PARSERS: list[BrokerParser] = [SchwabParser(), SchwabRealizedGLParser()]


def detect_broker(headers: list[str]) -> BrokerParser | None:
    for p in PARSERS:
        if p.detect(headers):
            return p
    return None
