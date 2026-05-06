from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from net_alpha.db.tables import LossCarryforwardRow


def test_row_constructs_with_minimum_fields():
    row = LossCarryforwardRow(
        year=2025,
        st_amount=Decimal("100.00"),
        lt_amount=Decimal("0"),
        source="user",
        updated_at=datetime(2026, 5, 5, 12, 0, 0),
    )
    assert row.year == 2025
    assert row.st_amount == Decimal("100.00")
    assert row.source == "user"


def test_row_rejects_negative_amounts():
    with pytest.raises(ValidationError):
        LossCarryforwardRow(
            year=2025,
            st_amount=Decimal("-1"),
            lt_amount=Decimal("0"),
            source="user",
            updated_at=datetime(2026, 5, 5, 12, 0, 0),
        )
    with pytest.raises(ValidationError):
        LossCarryforwardRow(
            year=2025,
            st_amount=Decimal("0"),
            lt_amount=Decimal("-1"),
            source="user",
            updated_at=datetime(2026, 5, 5, 12, 0, 0),
        )
