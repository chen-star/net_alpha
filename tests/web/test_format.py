from net_alpha.web.format import fmt_days_held


def test_fmt_days_held_short():
    assert fmt_days_held(0) == "0d"
    assert fmt_days_held(330) == "330d"
    assert fmt_days_held(364) == "364d"


def test_fmt_days_held_medium():
    assert fmt_days_held(365) == "1.0y"
    # 548 / 365.25 = 1.5004... → "1.5y"
    assert fmt_days_held(548) == "1.5y"
    # 1000 / 365.25 = 2.7378... → "2.7y"
    assert fmt_days_held(1000) == "2.7y"


def test_fmt_days_held_long():
    # 1095 / 365.25 = 2.9979... — boundary case lives in the "medium" bucket
    # because the bucket gate is `years < 3`, not `days >= 1095`.
    # Slightly above the boundary clearly lands in the long bucket:
    assert fmt_days_held(1100) == "3y"
    assert fmt_days_held(1931) == "5y"
    assert fmt_days_held(3650) == "10y"


def test_fmt_days_held_none():
    assert fmt_days_held(None) == "—"
