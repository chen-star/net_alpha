from datetime import datetime
from decimal import Decimal

import pytest

from net_alpha.targets.models import PositionTarget, TargetUnit


def test_target_unit_values():
    assert TargetUnit.USD.value == "usd"
    assert TargetUnit.SHARES.value == "shares"


def test_position_target_constructs():
    t = PositionTarget(
        symbol="HIMS",
        target_amount=Decimal("1000"),
        target_unit=TargetUnit.USD,
        created_at=datetime(2026, 4, 29, 10, 0, 0),
        updated_at=datetime(2026, 4, 29, 10, 0, 0),
    )
    assert t.symbol == "HIMS"
    assert t.target_unit == TargetUnit.USD


def test_position_target_is_frozen():
    t = PositionTarget(
        symbol="HIMS",
        target_amount=Decimal("1000"),
        target_unit=TargetUnit.USD,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    with pytest.raises((AttributeError, Exception)):
        t.symbol = "OTHER"  # type: ignore[misc]
