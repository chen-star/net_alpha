"""P — wash-sale explanation surface (pure functions + templates)."""

from net_alpha.explain.exempt import explain_exempt
from net_alpha.explain.violation import (
    AccountPair,
    ExplanationModel,
    LotRef,
    TradeRow,
    explain_violation,
)

__all__ = [
    "AccountPair",
    "ExplanationModel",
    "LotRef",
    "TradeRow",
    "explain_violation",
    "explain_exempt",
]
