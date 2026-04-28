from datetime import date, timedelta
from decimal import Decimal

from net_alpha.models.domain import Trade
from net_alpha.portfolio.tax_planner import (
    PlannedTrade,
    TaxBrackets,
    TaxLightSignal,
    assess_trade,
)


def test_tax_light_signal_constructs() -> None:
    s = TaxLightSignal(
        color="green",
        reason_codes=["LT_LOSS"],
        explanation="Tax-efficient — LT loss; offsets ST gains",
        suggestion=None,
        lot_method_recommended="HIFO",
    )
    assert s.color == "green"
