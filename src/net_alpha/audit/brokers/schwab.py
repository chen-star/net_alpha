from __future__ import annotations

from net_alpha.audit.brokers.base import BrokerGLProvider, BrokerLot
from net_alpha.db.repository import Repository


class SchwabGLProvider(BrokerGLProvider):
    """Reads broker-supplied lot detail from imported Schwab Realized G/L CSVs."""

    def __init__(self, repo: Repository):
        self._repo = repo

    def supports(self, account_id: int) -> bool:
        for a in self._repo.list_accounts():
            if a.id == account_id and a.broker == "Schwab":
                return True
        return False

    def get_lot_detail(self, account_id: int, symbol: str) -> list[BrokerLot]:
        gl_lots = self._repo.get_gl_lots_for_ticker(account_id, symbol)
        return [
            BrokerLot(
                symbol=lot.ticker,
                account_id=account_id,
                acquired=lot.opened_date,
                closed=lot.closed_date,
                qty=lot.quantity,
                cost_basis=lot.cost_basis,
                proceeds=lot.proceeds,
                wash_disallowed=lot.disallowed_loss if lot.wash_sale else None,
                source_label="Schwab Realized G/L",
            )
            for lot in gl_lots
        ]
